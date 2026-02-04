"""FastAPI application structure.

This module initializes and configures the FastAPI application.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from src.english_tutor.api.admin import router as admin_router
from src.english_tutor.api.bot import get_bot_application, remove_webhook, setup_webhook
from src.english_tutor.api.content.questions import router as questions_router
from src.english_tutor.api.content.questions_by_id import router as questions_by_id_router
from src.english_tutor.api.content.tasks import router as tasks_router
from src.english_tutor.api.sync import router as sync_router
from src.english_tutor.config import get_settings
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


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
    import asyncio

    logger.info("FastAPI application starting up")

    # Run migrations on startup as a safety fallback
    # (release_command should handle this, but this ensures it happens)
    run_migrations()

    # Set up Telegram webhook if webhook URL is configured
    # Do this in background task to avoid blocking startup
    webhook_setup_task = None
    if settings.telegram_webhook_url:
        webhook_path = "/webhook"
        webhook_url = f"{settings.telegram_webhook_url.rstrip('/')}{webhook_path}"

        async def setup_webhook_background():
            """Set up webhook in background to avoid blocking startup."""
            try:
                await setup_webhook(webhook_url)
                logger.info(f"Telegram webhook configured at {webhook_url}")
            except Exception as e:
                logger.error(f"Failed to set up Telegram webhook: {e}", exc_info=True)

        # Start webhook setup in background
        webhook_setup_task = asyncio.create_task(setup_webhook_background())
    else:
        logger.info("TELEGRAM_WEBHOOK_URL not set, webhook mode disabled")

    # Track if scheduler was started so we can stop it on shutdown
    scheduler_enabled = os.getenv("ENABLE_SYNC_SCHEDULER", "false").lower() == "true"
    if scheduler_enabled:
        from src.english_tutor.services.scheduler import start_scheduler

        start_scheduler()
    try:
        yield
    finally:
        logger.info("FastAPI application shutting down")
        # Cancel webhook setup task if still running
        if webhook_setup_task and not webhook_setup_task.done():
            webhook_setup_task.cancel()
            try:
                await webhook_setup_task
            except asyncio.CancelledError:
                pass
        # Remove webhook on shutdown
        if settings.telegram_webhook_url:
            try:
                await remove_webhook()
            except Exception as e:
                logger.warning(f"Error removing webhook on shutdown: {e}")
        # Only stop scheduler if it was started
        if scheduler_enabled:
            from src.english_tutor.services.scheduler import stop_scheduler

            stop_scheduler()


app = FastAPI(
    title="English Tutor API",
    description="Content management API for English Tutor Telegram Bot",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

# Register routers
app.include_router(tasks_router)
app.include_router(questions_router)
app.include_router(questions_by_id_router)
app.include_router(sync_router)
app.include_router(admin_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint for health checks."""
    return {"status": "ok", "service": "English Tutor API"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/webhook")
async def telegram_webhook(request: Request) -> Response:
    """Telegram webhook endpoint to receive updates.

    This endpoint receives POST requests from Telegram with bot updates.
    """
    if not settings.telegram_webhook_url:
        return JSONResponse(
            status_code=503,
            content={"error": "Webhook mode not configured"},
        )

    try:
        bot_app = get_bot_application()
        update_data = await request.json()

        # Parse the update and process it
        from telegram import Update

        update = Update.de_json(update_data, bot_app.bot)
        await bot_app.process_update(update)

        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Error processing webhook update: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"},
        )
