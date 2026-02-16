"""
Queue Outbox Processor
======================

Generic outbox pipeline: poll Postgres outbox, call domain handlers (notifications, email, etc.).
Uses Celery + Redis + Postgres; no Kafka in this path. Notifications provide only the handler.

Key Features:
    - Periodic processing of registered outbox queues
    - Automatic retry and dead letter (in backend)
    - Configurable interval and graceful shutdown
"""

import asyncio
from typing import Optional

from app.core.logger import get_logger

from app.services.queue.generic_outbox_processor import (
    process_notification_outbox_batch,
    register_outbox,
)
from app.services.queue.outbox_backends.notification_backend import NotificationOutboxBackend
from app.services.notifications.outbox_service import (
    mark_notification_dead_letter_callback,
    process_notification_payload,
)

logger = get_logger(__name__)

_processor_task: Optional[asyncio.Task] = None
_processor_running = False
_processor_interval = 5
_registered = False


def _ensure_notification_outbox_registered() -> None:
    global _registered
    if _registered:
        return
    backend = NotificationOutboxBackend(on_dead_letter=mark_notification_dead_letter_callback)
    register_outbox("notification", backend, process_notification_payload)
    _registered = True


async def _process_outbox_loop() -> None:
    global _processor_running
    _ensure_notification_outbox_registered()
    logger.info("Outbox processor started")
    _processor_running = True
    while _processor_running:
        try:
            stats = await process_notification_outbox_batch(limit=20)
            if stats.get("processed", 0) > 0 or stats.get("retries", 0) > 0:
                logger.info(
                    "Outbox processing cycle: processed=%s, completed=%s, failed=%s, retries=%s",
                    stats.get("processed", 0),
                    stats.get("completed", 0),
                    stats.get("failed", 0),
                    stats.get("retries", 0),
                )
            await asyncio.sleep(_processor_interval)
        except asyncio.CancelledError:
            logger.info("Outbox processor cancelled")
            break
        except Exception as e:
            logger.error("Error in outbox processor loop: %s", e, exc_info=True)
            await asyncio.sleep(_processor_interval * 2)
    logger.info("Outbox processor stopped")
    _processor_running = False


async def start_outbox_processor(interval: int = 5) -> None:
    """Start the outbox processor background task."""
    global _processor_task, _processor_interval, _processor_running
    if _processor_running:
        logger.warning("Outbox processor is already running")
        return
    _processor_interval = interval
    _processor_task = asyncio.create_task(_process_outbox_loop())
    logger.info("Outbox processor started with %ss interval", interval)


async def stop_outbox_processor() -> None:
    """Stop the outbox processor background task."""
    global _processor_task, _processor_running
    if not _processor_running:
        return
    _processor_running = False
    if _processor_task:
        _processor_task.cancel()
        try:
            await _processor_task
        except asyncio.CancelledError:
            pass
    logger.info("Outbox processor stopped")


def is_processor_running() -> bool:
    """Check if the outbox processor is currently running."""
    return _processor_running


async def process_outbox_manually(limit: int = 10) -> dict:
    """Manually trigger notification outbox processing. Returns processing statistics."""
    _ensure_notification_outbox_registered()
    return await process_notification_outbox_batch(limit=limit)
