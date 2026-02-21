import os
import pdfplumber
from docx import Document
from typing import Optional
import logging
from datetime import datetime
import uuid

from app.config import settings
from app.core.extractors.free_extractor import FreeExtractor  # Changed from ai_extractor
from app.core.extractors.pattern_extractor import PatternExtractor
from app.models.financial import FinancialExtractionResult
from app.models.document import DocumentType
from app.utils.excel_generator import ExcelGenerator

logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self):
        # Use free extractor instead of AI extractor
        self.free_extractor = FreeExtractor()  # New free extractor
        self.pattern_extractor = PatternExtractor()  # Keep as fallback
        self.excel_generator = ExcelGenerator()
    
    async def process_document(self, file_path: str, filename: str) -> Optional[str]:
        """Process uploaded document and extract financial data"""
        try:
            # Extract text from document
            text = await self._extract_text(file_path, filename)
            if not text:
                logger.error(f"Failed to extract text from {filename}")
                return None
            
            # Extract financial data using free methods
            extraction_result = await self._extract_financial_data(text, filename)
            
            # Generate Excel file
            output_filename = f"{uuid.uuid4()}_extraction.xlsx"
            output_path = os.path.join(settings.output_dir, output_filename)
            
            self.excel_generator.generate(extraction_result, output_path)
            
            return output_filename
            
        except Exception as e:
            logger.error(f"Error processing document {filename}: {str(e)}")
            return None
    
    async def _extract_text(self, file_path: str, filename: str) -> Optional[str]:
        """Extract text from various document formats"""
        file_ext = os.path.splitext(filename)[1].lower()
        
        try:
            if file_ext == '.pdf':
                return await self._extract_from_pdf(file_path)
            elif file_ext == '.docx':
                return await self._extract_from_docx(file_path)
            elif file_ext == '.txt':
                return await self._extract_from_txt(file_path)
            else:
                logger.error(f"Unsupported file type: {file_ext}")
                return None
                
        except Exception as e:
            logger.error(f"Text extraction failed: {str(e)}")
            return None
    
    async def _extract_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF"""
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    
    async def _extract_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX"""
        doc = Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text
    
    async def _extract_from_txt(self, file_path: str) -> str:
        """Extract text from TXT"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    async def _extract_financial_data(self, text: str, filename: str) -> FinancialExtractionResult:
        """Extract financial data using free extractors"""
        
        # Try free extractor first (custom built for your formats)
        try:
            logger.info("Attempting extraction with free extractor")
            result = await self.free_extractor.extract(text)
            result.document_name = filename
            result.extraction_date = datetime.now().isoformat()
            
            # Check if free extractor found any data
            if result.data and any(result.data.values()):
                logger.info("Free extractor successfully extracted data")
                return result
            else:
                logger.info("Free extractor found no data, trying pattern matching")
        except Exception as e:
            logger.warning(f"Free extractor failed: {str(e)}")
        
        # Fallback to pattern matching
        logger.info("Using pattern matching as fallback")
        result = await self.pattern_extractor.extract(text)
        result.document_name = filename
        result.extraction_date = datetime.now().isoformat()
        return result