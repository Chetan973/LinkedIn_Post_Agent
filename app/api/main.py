"""FastAPI application entry point with lifecycle management."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup and shutdown."""
    # Startup: Initialize database
    await init_db()
    print("✓ Database initialized")
    yield
    # Shutdown: Cleanup if needed
    print("✓ Application shutting down")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "LinkedIn AI Agent",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "database": "sqlite",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
