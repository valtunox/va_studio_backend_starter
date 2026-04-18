"""
Queue Background Tasks
======================

Background jobs for agent runs, outbox processing, and other queue-driven work.
Uses the shared Celery app from core; broker config from queue.broker.

Tasks:
  - process_outbox_batch: Process a batch of outbox entries (notification outbox via notifications.outbox_service)
  - run_agent_async: Enqueue an agent run for async execution (optional)
"""

import asyncio
from typing import Any, Dict, Optional

from app.core.logger import get_logger

logger = get_logger(__name__)

# Use core Celery app so one worker can run queue + notifications + messaging tasks
try:
    from app.core.celery_app import celery as celery_app
except ImportError:
    celery_app = None


def process_outbox_batch(limit: int = 20) -> Dict[str, Any]:
    """
    Process a batch of outbox entries (e.g. notification outbox).
    Calls the outbox processor service; typically the outbox_processor loop runs
    in-app, but this task allows on-demand or scheduled batch processing.

    Args:
        limit: Max number of entries to process per batch.

    Returns:
        Dict with processed, completed, failed, retries counts.
    """
    if limit <= 0:
        return {"processed": 0, "completed": 0, "failed": 0, "retries": 0}
    try:
        from app.services.queue.outbox_processor import process_outbox_manually
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(process_outbox_manually(limit=limit))
            return result
        finally:
            loop.close()
    except Exception as e:
        logger.error("queue.process_outbox_batch failed: %s", e, exc_info=True)
        return {"processed": 0, "completed": 0, "failed": 1, "retries": 0, "error": str(e)}


def run_agent(
    agent_key: str,
    query: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    model: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run an AI agent in the background (async job).
    Dispatches to the agent handler and returns result metadata.

    Args:
        agent_key: Handler key (e.g. networking, marketing, code).
        query: User query.
        user_id: Optional user id.
        session_id: Optional session id.
        model: Optional model override.
        context: Optional context dict.

    Returns:
        Dict with status, agent_type, response excerpt, or error.
    """
    try:
        from app.services.ai.ai_services_router import _get_agent_handler
        handler = _get_agent_handler(agent_key)
        if not handler:
            return {"status": "error", "error": f"Agent {agent_key} not available"}
        event = {
            "query": query,
            "user_id": user_id or "anonymous",
            "session_id": session_id,
            "model": model,
            "context": context or {},
        }
        result = handler(event)
        status_code = result.get("statusCode", 200)
        body = result.get("body", "{}")
        if isinstance(body, str):
            import json
            try:
                body = json.loads(body)
            except Exception:
                body = {"response": body}
        return {
            "status": "success" if status_code == 200 else "error",
            "status_code": status_code,
            "agent_type": body.get("agent_type", agent_key),
            "response_excerpt": (body.get("response") or "")[:500],
        }
    except Exception as e:
        logger.error("queue.run_agent failed: %s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


# Register with Celery when app is available (assign back so .delay() works)
if celery_app is not None:
    process_outbox_batch = celery_app.task(name="queue.process_outbox_batch")(process_outbox_batch)
    run_agent = celery_app.task(name="queue.run_agent")(run_agent)
