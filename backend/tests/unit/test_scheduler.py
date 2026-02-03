"""Unit tests for standalone scheduler.

Tests for scheduler independence, configuration via environment variables,
and graceful shutdown.
"""

import os
from unittest import mock

from src.english_tutor.services.scheduler import (
    get_scheduler,
    start_scheduler,
    stop_scheduler,
)


class TestScheduler:
    """Test suite for standalone scheduler."""

    def teardown_method(self):
        """Clean up scheduler after each test."""
        stop_scheduler()

    def test_scheduler_starts_independently(self):
        """Test that scheduler can start independently without other services."""
        # Given: A fresh scheduler instance
        with mock.patch(
            "src.english_tutor.services.scheduler.ContentSyncService"
        ) as mock_sync_service:
            mock_sync_service.return_value.sync_all = mock.Mock()

            # When: Starting the scheduler
            start_scheduler()

            # Then: Scheduler should be running
            scheduler = get_scheduler()
            assert scheduler.running is True
            assert len(scheduler.get_jobs()) == 1
            assert scheduler.get_job("content_sync") is not None

    def test_scheduler_stops_gracefully(self):
        """Test that scheduler stops gracefully without errors."""
        # Given: A running scheduler
        with mock.patch(
            "src.english_tutor.services.scheduler.ContentSyncService"
        ) as mock_sync_service:
            mock_sync_service.return_value.sync_all = mock.Mock()
            start_scheduler()
            scheduler = get_scheduler()
            assert scheduler.running is True

            # When: Stopping the scheduler
            stop_scheduler()

            # Then: Scheduler should be stopped
            new_scheduler = get_scheduler()
            assert new_scheduler.running is False

    def test_scheduler_reads_config_from_env(self):
        """Test that scheduler reads sync interval from SYNC_INTERVAL_MINUTES env var."""
        # Given: SYNC_INTERVAL_MINUTES is set to 30
        with mock.patch.dict(os.environ, {"SYNC_INTERVAL_MINUTES": "30"}):
            with mock.patch(
                "src.english_tutor.services.scheduler.ContentSyncService"
            ) as mock_sync_service:
                mock_sync_service.return_value.sync_all = mock.Mock()

                # When: Starting the scheduler
                start_scheduler()

                # Then: Job should be scheduled with 30-minute interval
                scheduler = get_scheduler()
                job = scheduler.get_job("content_sync")
                assert job is not None
                # Check the trigger configuration - CronTrigger stores minute field
                trigger = job.trigger
                assert "30" in str(trigger)

    def test_scheduler_uses_default_interval_when_env_not_set(self):
        """Test that scheduler uses 60 minutes default when env var not set."""
        # Given: SYNC_INTERVAL_MINUTES is not set
        with mock.patch.dict(os.environ, {}, clear=True):
            # Ensure SYNC_INTERVAL_MINUTES is not in environment
            os.environ.pop("SYNC_INTERVAL_MINUTES", None)

            with mock.patch(
                "src.english_tutor.services.scheduler.ContentSyncService"
            ) as mock_sync_service:
                mock_sync_service.return_value.sync_all = mock.Mock()

                # When: Starting the scheduler
                start_scheduler()

                # Then: Job should be scheduled with default 60-minute interval
                scheduler = get_scheduler()
                job = scheduler.get_job("content_sync")
                assert job is not None
                trigger = job.trigger
                assert "60" in str(trigger)

    def test_scheduler_does_not_start_twice(self):
        """Test that starting scheduler twice doesn't create duplicate jobs."""
        # Given: A running scheduler
        with mock.patch(
            "src.english_tutor.services.scheduler.ContentSyncService"
        ) as mock_sync_service:
            mock_sync_service.return_value.sync_all = mock.Mock()
            start_scheduler()

            # When: Trying to start again
            start_scheduler()

            # Then: Should still have only one job
            scheduler = get_scheduler()
            assert scheduler.running is True
            assert len(scheduler.get_jobs()) == 1

    def test_stop_scheduler_when_not_running(self):
        """Test that stopping a non-running scheduler doesn't cause errors."""
        # Given: Scheduler is not running
        # (teardown ensures it's stopped from previous test)

        # When: Stopping the scheduler
        stop_scheduler()

        # Then: No error should occur (implicit - test passes if no exception)

    def test_get_scheduler_creates_new_instance(self):
        """Test that get_scheduler creates a new instance if none exists."""
        # Given: No scheduler exists (ensured by teardown)

        # When: Getting scheduler
        scheduler = get_scheduler()

        # Then: A scheduler instance should be returned
        assert scheduler is not None
        from apscheduler.schedulers.background import BackgroundScheduler

        assert isinstance(scheduler, BackgroundScheduler)


class TestSchedulerAppIndependence:
    """Test suite for scheduler independence from FastAPI app lifecycle."""

    def teardown_method(self):
        """Clean up scheduler after each test."""
        stop_scheduler()

    def test_app_starts_without_scheduler(self):
        """Test that FastAPI app can start without the scheduler.

        When ENABLE_SYNC_SCHEDULER is set to 'false', the app should start
        without initializing the scheduler, demonstrating decoupling.
        """
        # Given: ENABLE_SYNC_SCHEDULER is explicitly disabled
        with mock.patch.dict(os.environ, {"ENABLE_SYNC_SCHEDULER": "false"}):
            # When: Importing and creating the app (simulating app initialization)
            # We mock the lifespan context to test the conditional logic
            from fastapi import FastAPI

            from src.english_tutor.api.app import lifespan

            test_app = FastAPI()

            # Mock start_scheduler to track if it gets called
            with mock.patch("src.english_tutor.api.app.start_scheduler") as mock_start:
                with mock.patch("src.english_tutor.api.app.stop_scheduler"):
                    with mock.patch("src.english_tutor.api.app.run_migrations"):
                        with mock.patch("src.english_tutor.api.app.settings") as mock_settings:
                            mock_settings.telegram_webhook_url = None
                            mock_settings.debug = False

                            import asyncio

                            async def run_lifespan():
                                async with lifespan(test_app):
                                    # Then: start_scheduler should NOT be called
                                    mock_start.assert_not_called()

                            asyncio.get_event_loop().run_until_complete(run_lifespan())

    def test_scheduler_runs_without_app(self):
        """Test that scheduler can run independently without FastAPI app.

        The scheduler should be able to start and run its jobs without
        requiring the FastAPI application to be initialized or running.
        """
        # Given: No FastAPI app is running, just the scheduler module
        with mock.patch(
            "src.english_tutor.services.scheduler.ContentSyncService"
        ) as mock_sync_service:
            mock_sync_service.return_value.sync_all = mock.Mock()

            # When: Starting the scheduler directly (not through app lifespan)
            start_scheduler()

            # Then: Scheduler should be running independently
            scheduler = get_scheduler()
            assert scheduler.running is True
            assert scheduler.get_job("content_sync") is not None

            # Verify the sync service was instantiated (scheduler works alone)
            mock_sync_service.assert_called_once()

            # And: The scheduler operates without any FastAPI imports needed
            # (The scheduler module only depends on apscheduler and content_sync)

    def test_app_enabled_scheduler_starts(self):
        """Test that scheduler starts when ENABLE_SYNC_SCHEDULER is true.

        This is the inverse test to verify the conditional logic works both ways.
        """
        # Given: ENABLE_SYNC_SCHEDULER is explicitly enabled
        with mock.patch.dict(os.environ, {"ENABLE_SYNC_SCHEDULER": "true"}):
            from fastapi import FastAPI

            from src.english_tutor.api.app import lifespan

            test_app = FastAPI()

            # When: Running the app lifespan with scheduler enabled
            with mock.patch("src.english_tutor.api.app.start_scheduler") as mock_start:
                with mock.patch("src.english_tutor.api.app.stop_scheduler"):
                    with mock.patch("src.english_tutor.api.app.run_migrations"):
                        with mock.patch("src.english_tutor.api.app.settings") as mock_settings:
                            mock_settings.telegram_webhook_url = None
                            mock_settings.debug = False

                            import asyncio

                            async def run_lifespan():
                                async with lifespan(test_app):
                                    # Then: start_scheduler SHOULD be called
                                    mock_start.assert_called_once()

                            asyncio.get_event_loop().run_until_complete(run_lifespan())
