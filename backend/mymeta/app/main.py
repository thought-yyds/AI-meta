from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1.router import api_router
from app.core.middleware import ErrorMiddleware
from app.core.logging import setup_logging

# Import all models to ensure they are registered with Base.metadata
from app.models.models import User, Session, Message, Summary  # noqa: F401

# Create database tables
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Create all database tables
    Base.metadata.create_all(bind=engine)
    setup_logging()
    yield
    # Shutdown
    pass

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=settings.description,
    lifespan=lifespan
)

# Add CORS middleware (must be before ErrorMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Add error handling middleware
app.add_middleware(ErrorMiddleware)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.version,
        "docs": "/docs",
        "health": "/api/v1/health/"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.app_name}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )