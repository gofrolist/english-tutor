"""FastAPI application structure.

This module initializes and configures the FastAPI application.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.english_tutor.api.content.questions import router as questions_router
from src.english_tutor.api.content.questions_by_id import router as questions_by_id_router
from src.english_tutor.api.content.tasks import router as tasks_router
from src.english_tutor.api.sync import router as sync_router
from src.english_tutor.config import DEBUG
from src.english_tutor.services.scheduler import start_scheduler, stop_scheduler
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan (startup/shutdown)."""
    logger.info("FastAPI application starting up")
    if os.getenv("ENABLE_SYNC_SCHEDULER", "false").lower() == "true":
        start_scheduler()
    try:
        yield
    finally:
        logger.info("FastAPI application shutting down")
        stop_scheduler()


app = FastAPI(
    title="English Tutor API",
    description="Content management API for English Tutor Telegram Bot",
    version="0.1.0",
    debug=DEBUG,
    lifespan=lifespan,
)

# Register routers
app.include_router(tasks_router)
app.include_router(questions_router)
app.include_router(questions_by_id_router)
app.include_router(sync_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint for health checks."""
    return {"status": "ok", "service": "English Tutor API"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
