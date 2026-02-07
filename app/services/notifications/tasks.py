"""
Notification Tasks

Celery tasks for async notification processing.
"""

from app.core.celery_app import celery_app
from app.core.database import get_db_context
from app.core.logger import get_logger
from app.services.notifications.service import NotificationService
from app.schemas.notification import NotificationCreate


logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3)
def send_notification_task(
    self,
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "info",
    action_url: str = None,
    reference_type: str = None,
    reference_id: str = None,
):
    """
    Celery task to create notification asynchronously.

    Args:
        user_id: Target user ID
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        action_url: Optional action URL
        reference_type: Optional reference type
        reference_id: Optional reference ID
    """
    import asyncio

    async def create_notification():
        async with get_db_context() as db:
            service = NotificationService(db)
            notification_data = NotificationCreate(
                title=title,
                message=message,
                type=notification_type,
                action_url=action_url,
                reference_type=reference_type,
                reference_id=reference_id,
            )
            await service.create(user_id, notification_data)

    try:
        asyncio.run(create_notification())
        logger.info(f"Notification sent to user {user_id}: {title}")
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def send_bulk_notifications_task(
    self,
    user_ids: list[str],
    title: str,
    message: str,
    notification_type: str = "info",
):
    """
    Celery task to send notifications to multiple users.

    Args:
        user_ids: List of target user IDs
        title: Notification title
        message: Notification message
        notification_type: Type of notification
    """
    import asyncio

    async def create_notifications():
        async with get_db_context() as db:
            service = NotificationService(db)
            notification_data = NotificationCreate(
                title=title,
                message=message,
                type=notification_type,
            )
            for user_id in user_ids:
                await service.create(user_id, notification_data)

    try:
        asyncio.run(create_notifications())
        logger.info(f"Bulk notifications sent to {len(user_ids)} users")
    except Exception as e:
        logger.error(f"Failed to send bulk notifications: {e}")
        raise self.retry(exc=e, countdown=60)


def notify_user(
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "info",
    action_url: str = None,
    reference_type: str = None,
    reference_id: str = None,
    delay: int = 0,
):
    """
    Helper function to queue notification.

    Args:
        user_id: Target user ID
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        action_url: Optional action URL
        reference_type: Optional reference type
        reference_id: Optional reference ID
        delay: Delay in seconds before sending
    """
    task = send_notification_task.apply_async(
        args=[user_id, title, message, notification_type, action_url, reference_type, reference_id],
        countdown=delay,
    )
    return task.id


def notify_users(
    user_ids: list[str],
    title: str,
    message: str,
    notification_type: str = "info",
):
    """
    Helper function to queue bulk notifications.

    Args:
        user_ids: List of target user IDs
        title: Notification title
        message: Notification message
        notification_type: Type of notification
    """
    task = send_bulk_notifications_task.apply_async(
        args=[user_ids, title, message, notification_type],
    )
    return task.id
