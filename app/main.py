from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.api.routes import router
from app.config import settings


# CREATE, UPLOAD AND OUTPUT DIRECTORIES
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.output_dir, exist_ok=True)

app = FastAPI(
    title = "Financial Document Analysis Portal",
    description = "A portal for uploading financial documents and extracting key information using AI.",
    version = "1.0.0"   
)

# CONFIGURE CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], #(AS OF NOW, ALLOWING ALL ORIGINS FOR DEVELOPMENT; SHOULD BE RESTRICTED IN PRODUCTION)
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

#INCLUDE ROUTERS
app.include_router(router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "message": "Welcome to the Financial Document Analysis Portal API. Please refer to /docs for API documentation.",
        "version": "1.0.0",
        "docs": "/docs"
    }
    
@app.get("/health")
async def health_check():
    return {"status": "healthy"}