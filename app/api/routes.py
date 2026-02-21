from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
import shutil
import os
import uuid
from datetime import datetime
import logging

from app.config import settings
from app.models.document import UploadResponse, ExtractionResponse, ExtractionStatus
from app.core.document_processor import DocumentProcessor

router = APIRouter()
logger = logging.getLogger(__name__)

# Store processing tasks (in production, use a proper task queue)
processing_tasks = {}

@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """Upload a document for processing"""
    
    # Validate file type
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file_ext} not allowed. Allowed types: {settings.allowed_extensions}"
        )
    
    # Validate file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset position
    
    if file_size > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {settings.max_file_size} bytes"
        )
    
    # Generate unique filename
    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}{file_ext}"
    file_path = os.path.join(settings.upload_dir, safe_filename)
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save file: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save file")
    
    return UploadResponse(
        filename=file.filename,
        file_id=file_id,
        document_type=file_ext[1:],  # Remove dot
        size=file_size,
        upload_time=datetime.now()
    )

@router.post("/extract/{file_id}", response_model=ExtractionResponse)
async def extract_document(
    file_id: str,
    background_tasks: BackgroundTasks
):
    """Extract financial data from uploaded document"""
    
    # Find the file
    file_path = None
    original_filename = None
    for ext in settings.allowed_extensions:
        potential_path = os.path.join(settings.upload_dir, f"{file_id}{ext}")
        if os.path.exists(potential_path):
            file_path = potential_path
            original_filename = f"document{ext}"
            break
    
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Create task
    task_id = str(uuid.uuid4())
    processing_tasks[task_id] = {
        "status": ExtractionStatus.PENDING,
        "file_id": file_id,
        "file_path": file_path,
        "original_filename": original_filename
    }
    
    # Start processing in background
    background_tasks.add_task(process_document_task, task_id, file_path, original_filename)
    
    return ExtractionResponse(
        task_id=task_id,
        status=ExtractionStatus.PENDING,
        message="Extraction started"
    )

@router.get("/status/{task_id}", response_model=ExtractionResponse)
async def get_extraction_status(task_id: str):
    """Get status of extraction task"""
    
    if task_id not in processing_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = processing_tasks[task_id]
    
    return ExtractionResponse(
        task_id=task_id,
        status=task["status"],
        message=task.get("message"),
        output_file=task.get("output_file")
    )

@router.get("/download/{filename}")
async def download_file(filename: str):
    """Download generated Excel file"""
    
    file_path = os.path.join(settings.output_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename
    )

@router.get("/debug/file/{file_id}")
async def debug_file_content(file_id: str):
    """Debug endpoint to see raw file content"""
    # Find the file
    file_path = None
    file_ext = None
    for ext in settings.allowed_extensions:
        potential_path = os.path.join(settings.upload_dir, f"{file_id}{ext}")
        if os.path.exists(potential_path):
            file_path = potential_path
            file_ext = ext
            break
    
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Read file content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Return as JSON
        return JSONResponse(
            content={
                "file_id": file_id,
                "file_path": file_path,
                "file_ext": file_ext,
                "file_size": os.path.getsize(file_path),
                "content": content,
                "lines": content.split('\n'),
                "line_count": len(content.split('\n'))
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

@router.get("/debug/tasks")
async def debug_tasks():
    """Debug endpoint to see all tasks"""
    tasks = {}
    for task_id, task in processing_tasks.items():
        tasks[task_id] = {
            "status": task["status"].value if hasattr(task["status"], "value") else task["status"],
            "file_id": task["file_id"],
            "has_output": task.get("output_file") is not None
        }
    return JSONResponse(content={"tasks": tasks, "count": len(tasks)})

async def process_document_task(task_id: str, file_path: str, original_filename: str):
    """Background task to process document"""
    
    try:
        # Update status
        processing_tasks[task_id]["status"] = ExtractionStatus.PROCESSING
        logger.info(f"Starting processing for task {task_id}, file: {file_path}")
        
        # Process document
        processor = DocumentProcessor()
        output_filename = await processor.process_document(file_path, original_filename)
        
        if output_filename:
            processing_tasks[task_id].update({
                "status": ExtractionStatus.COMPLETED,
                "output_file": output_filename,
                "message": "Extraction completed successfully"
            })
            logger.info(f"Task {task_id} completed successfully, output: {output_filename}")
        else:
            processing_tasks[task_id].update({
                "status": ExtractionStatus.FAILED,
                "message": "Failed to extract data from document"
            })
            logger.error(f"Task {task_id} failed: no output filename returned")
            
    except Exception as e:
        logger.error(f"Processing failed for task {task_id}: {str(e)}", exc_info=True)
        processing_tasks[task_id].update({
            "status": ExtractionStatus.FAILED,
            "message": f"Processing error: {str(e)}"
        })