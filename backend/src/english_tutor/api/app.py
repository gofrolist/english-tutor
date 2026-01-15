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


def run_migrations() -> None:
    """Run database migrations if needed.

    This is a safety fallback in case release_command didn't run.
    Migrations are idempotent, so running them multiple times is safe.

    Note: The local alembic/ directory may shadow the installed package.
    If migrations fail to import, run them manually with: make migrate
    """
    try:
        import sys
        from pathlib import Path

        # Temporarily remove current directory from sys.path to avoid shadowing
        # The local alembic/ directory shadows the installed alembic package
        backend_dir = Path(__file__).parent.parent.parent.parent
        current_dir_str = str(backend_dir.resolve())
        path_removed = False

        try:
            if current_dir_str in sys.path:
                sys.path.remove(current_dir_str)
                path_removed = True

            from alembic.config import Config

            from alembic import command
        except ImportError:
            # If import fails, restore path and skip migrations
            # This is expected when local alembic/ directory shadows the package
            return
        finally:
            if path_removed and current_dir_str not in sys.path:
                sys.path.insert(0, current_dir_str)

        alembic_ini_path = backend_dir / "alembic.ini"
        if not alembic_ini_path.exists():
            return

        alembic_cfg = Config(str(alembic_ini_path))
        alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed")
    except Exception:
        # Silently skip if migrations can't run (e.g., due to import shadowing)
        # Migrations should be run manually with: make migrate
        pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan (startup/shutdown)."""
    logger.info("FastAPI application starting up")

    # Run migrations on startup as a safety fallback
    # (release_command should handle this, but this ensures it happens)
    run_migrations()

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
