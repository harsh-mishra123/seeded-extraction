from fastapi import APIRouter, HTTPException
import os
from app.config import settings

router = APIRouter(prefix="/debug", tags=["debug"])

@router.get("/file/{file_id}")
async def get_file_content(file_id: str):
    """Debug: Get raw content of uploaded file"""
    # Find the file
    for ext in settings.allowed_extensions:
        file_path = os.path.join(settings.upload_dir, f"{file_id}{ext}")
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                content = f.read()
            return {
                "file_id": file_id,
                "content": content,
                "lines": content.split('\n')
            }
    raise HTTPException(status_code=404, detail="File not found")
