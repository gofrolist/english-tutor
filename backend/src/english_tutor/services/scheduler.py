"""Content sync scheduler.

Provides scheduled content synchronization from Google Sheets/Drive.
"""

import os
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.english_tutor.services.content_sync import ContentSyncService
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)

_scheduler: Optional[BackgroundScheduler] = None


def get_scheduler() -> BackgroundScheduler:
    """Get or create the global scheduler instance.

    Returns:
        BackgroundScheduler instance
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
        logger.info("Content sync scheduler created")
    return _scheduler


def start_scheduler() -> None:
    """Start the content sync scheduler.

    Reads sync interval from SYNC_INTERVAL_MINUTES environment variable.
    Defaults to 60 minutes if not set.
    """
    scheduler = get_scheduler()

    if scheduler.running:
        logger.warning("Scheduler is already running")
        return

    # Get sync interval from environment (in minutes)
    sync_interval = int(os.getenv("SYNC_INTERVAL_MINUTES", "60"))

    # Add sync job
    sync_service = ContentSyncService()
    scheduler.add_job(
        func=sync_service.sync_all,
        trigger=CronTrigger(minute=f"*/{sync_interval}"),  # Every N minutes
        id="content_sync",
        name="Content Sync from Google Sheets/Drive",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"Content sync scheduler started (interval: {sync_interval} minutes)")


def stop_scheduler() -> None:
    """Stop the content sync scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        logger.info("Content sync scheduler stopped")
    _scheduler = None
