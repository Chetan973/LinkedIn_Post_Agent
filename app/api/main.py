"""FastAPI application entry point with lifecycle management."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings
from app.db.database import init_db, get_checkpointer, close_checkpointer
from app.api.routers import posts


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup and shutdown."""
    # Startup: Initialize database and checkpointer
    await init_db()
    print("[OK] Database initialized")

    await get_checkpointer()
    print("[OK] LangGraph checkpointer initialized")

    yield

    # Shutdown: Close checkpointer and cleanup
    await close_checkpointer()
    print("[OK] LangGraph checkpointer closed")
    print("[OK] Application shutting down")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(posts.router, prefix="/api/v1")


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
        "database": "supabase",
        "agent": "langgraph",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
