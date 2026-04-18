"""
Generic outbox processor.
=========================

Queue-owned pipeline: poll outbox backends, call domain handlers, update status.
Fits any use case (notifications, email, cloud, etc.); transport is Celery + Redis + Postgres.
Other transports (e.g. Kafka) can be added later as alternative backends without changing this.
"""

from typing import Any, Dict, List

from app.core.logger import get_logger

from app.services.queue.outbox_backends.base import OutboxBackend, OutboxEntry, OutboxHandler

logger = get_logger(__name__)

# Registry: queue_name -> (backend, handler)
_backend_registry: Dict[str, tuple[OutboxBackend, OutboxHandler]] = {}


def register_outbox(queue_name: str, backend: OutboxBackend, handler: OutboxHandler) -> None:
    """Register an outbox backend and its domain handler. Call at app startup."""
    _backend_registry[queue_name] = (backend, handler)
    logger.info("Registered outbox queue=%s", queue_name)


def get_registered_queues() -> List[str]:
    """Return list of registered queue names."""
    return list(_backend_registry.keys())


async def process_entry(
    backend: OutboxBackend,
    handler: OutboxHandler,
    entry: OutboxEntry,
) -> bool:
    """Process one outbox entry: mark processing, run handler, mark completed or failed."""
    outbox_id = entry["id"]
    payload = entry.get("payload") or entry
    try:
        ok = await backend.mark_processing(outbox_id)
        if not ok:
            return False
        success = await handler(payload, entry)
        if success:
            await backend.mark_completed(outbox_id)
            return True
        await backend.mark_failed(
            outbox_id,
            "Handler returned False",
            error_code="PROCESSING_FAILED",
            retry=True,
        )
        return False
    except Exception as e:
        logger.exception("Outbox entry %s failed: %s", outbox_id, e)
        await backend.mark_failed(
            outbox_id,
            str(e),
            error_code=type(e).__name__,
            retry=True,
        )
        return False


async def process_batch_for_queue(queue_name: str, limit: int = 10) -> Dict[str, int]:
    """Process a batch of pending and retry entries for one queue. Returns stats."""
    stats = {"processed": 0, "completed": 0, "failed": 0, "retries": 0}
    reg = _backend_registry.get(queue_name)
    if not reg:
        logger.warning("No outbox registered for queue=%s", queue_name)
        return stats

    backend, handler = reg

    # Pending
    pending = await backend.get_pending_entries(limit=limit)
    stats["processed"] = len(pending)
    for entry in pending:
        success = await process_entry(backend, handler, entry)
        if success:
            stats["completed"] += 1
        else:
            stats["failed"] += 1

    # Retries
    retries = await backend.get_failed_retry_entries(limit=limit)
    stats["retries"] = len(retries)
    for entry in retries:
        await backend.reset_to_pending(entry["id"])
        success = await process_entry(backend, handler, entry)
        if success:
            stats["completed"] += 1
        else:
            stats["failed"] += 1

    return stats


async def process_batch_all_queues(limit_per_queue: int = 10) -> Dict[str, Dict[str, int]]:
    """Process a batch for every registered queue. Returns { queue_name: stats }."""
    result = {}
    for queue_name in _backend_registry:
        result[queue_name] = await process_batch_for_queue(queue_name, limit=limit_per_queue)
    return result


async def process_notification_outbox_batch(limit: int = 10) -> Dict[str, int]:
    """
    Process the notification outbox only. Convenience for backward compatibility.
    Uses the generic processor with the registered 'notification' queue.
    """
    return await process_batch_for_queue("notification", limit=limit)
