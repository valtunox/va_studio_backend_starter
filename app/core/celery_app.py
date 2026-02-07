"""
Celery Configuration

Celery app for background task processing.
"""

from celery import Celery

from app.core.settings import settings


# Create Celery app
celery_app = Celery(
    "va_studio",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=3600,  # 1 hour
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
)

# Auto-discover tasks from services
celery_app.autodiscover_tasks([
    "app.services.email",
    "app.services.notifications",
    "app.services.analytics",
])


@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery."""
    print(f"Request: {self.request!r}")
    return "Celery is working!"
