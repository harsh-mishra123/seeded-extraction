from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional

class Settings(BaseSettings):
    #API KEYS
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    #FILE SETTINGS
    upload_dir: str = "uploads"
    output_dir: str = "outputs"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: list = [".pdf", ".docx", ".txt"]
    
    #EXTRACTION SETTINGS
    use_ai_extraction: bool = True
    ai_model: str = "gpt-4"
    
    #SERVER SETTINGS
    host: str = "0.0.0.0"
    port: int = 8000
    
    model_config = ConfigDict(env_file=".env", extra = "ignore")

settings = Settings()