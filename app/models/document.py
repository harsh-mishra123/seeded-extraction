from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class DocumentType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"

class UploadResponse(BaseModel):
    filename: str
    file_id: str
    document_type: DocumentType
    size: int
    upload_time: datetime
    message: str = "File uploaded successfully"

class ExtractionRequest(BaseModel):
    file_id: str
    options: Optional[dict] = Field(default_factory=dict)

class ExtractionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ExtractionResponse(BaseModel):
    task_id: str
    status: ExtractionStatus
    message: Optional[str] = None
    output_file: Optional[str] = None