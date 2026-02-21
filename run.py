import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",  # This should be a string, not separated arguments
        host=settings.host,
        port=settings.port,
        reload=True
    )