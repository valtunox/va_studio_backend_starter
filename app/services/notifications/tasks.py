"""
Celery Tasks for Async Notification Processing
===============================================

This module provides Celery background tasks for asynchronous notification
processing. Tasks handle notification creation, broadcasting, and specialized
notification types like deployment and PDF processing notifications.

Tasks:
    - create_and_broadcast_notification: Create notification and broadcast via WebSocket
    - send_deployment_notification: Send deployment status notifications
    - send_pdf_processing_notification: Send PDF processing status notifications
    - batch_send_notifications: Send multiple notifications in batch

All tasks integrate with the notification service and WebSocket broadcasting
for real-time delivery.

Usage:
    from app.services.notifications.tasks import create_and_broadcast_notification
    create_and_broadcast_notification.delay(
        username="user123",
        title="Hello",
        message="World"
    )
"""

import os
from app.core.logger import get_logger
from typing import Dict, Any, Optional
from celery import Celery
from app.services.notifications.service import notification_service
from app.services.notifications.models import NotificationCreate
# Import dynamically to avoid circular imports if needed, but here it seems fine as websocket imports service logic
# Actually websocket imports service, tasks imports websocket. This might circle: 
# service -> models
# tasks -> service, models, websocket
# websocket -> service, models
# service doesn't import tasks/websocket. So this is fine.
# But router imports service and websocket (dynamically).
# It should be fine.
try:
    from app.services.notifications.websocket import broadcast_notification, broadcast_unread_count_update
except ImportError:
    # Fallback if websocket module issues
    pass

logger = get_logger(__name__)

# Get Redis URL for Celery broker
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Import shared Celery app
from app.core.celery_app import celery as celery_app

# Update configuration if needed (merging with core config)
celery_app.conf.update(
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
)


@celery_app.task(name='notifications.create_and_broadcast')
def create_and_broadcast_notification(
    username: str,
    title: str,
    message: str,
    notification_type: str = "info",
    priority: str = "normal",
    metadata: Optional[Dict[str, Any]] = None,
    channel_type: str = "in_app",
    recipient: Optional[str] = None
):
    """
    Create a notification and broadcast it via WebSocket (async task)
    
    Args:
        username: Username to send notification to
        title: Notification title
        message: Notification message
        notification_type: Type of notification (legacy)
        priority: Priority level
        metadata: Optional metadata
    """
    try:
        # Infer recipient
        recipient_val = recipient or username
        
        # Create notification
        notification_create = NotificationCreate(
            username=username,
            recipient=recipient_val,
            title=title,
            message=message,
            body=message,
            channel_type=channel_type,
            type=notification_type,
            priority=priority,
            metadata=metadata
        )
        
        import asyncio
        
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run async operations
        async def create_and_broadcast():
            notification = await notification_service.create_notification(notification_create)
            
            # Publish control plane event: kpi stage (notification created)
            try:
                from app.services.messaging.redis_pubsub import RedisPubSub
                from datetime import datetime
                redis_pubsub = RedisPubSub(REDIS_URL)
                await redis_pubsub.connect()
                await redis_pubsub.publish("control_plane:events", {
                    "type": "notification",
                    "event_type": "kpi",
                    "id": str(notification.id),
                    "username": username,
                    "title": title,
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "completed"
                })
                await redis_pubsub.close()
            except Exception as e:
                logger.warning(f"Failed to publish control plane kpi event: {e}")
            
            # Broadcast via WebSocket
            try:
                from app.services.notifications.websocket import broadcast_notification, broadcast_unread_count_update
                await broadcast_notification(notification)
                
                # Publish control plane event: output stage (notification delivered)
                try:
                    from app.services.messaging.redis_pubsub import RedisPubSub
                    from datetime import datetime
                    redis_pubsub = RedisPubSub(REDIS_URL)
                    await redis_pubsub.connect()
                    await redis_pubsub.publish("control_plane:events", {
                        "type": "notification",
                        "event_type": "output",
                        "id": str(notification.id),
                        "username": username,
                        "timestamp": datetime.utcnow().isoformat(),
                        "status": "completed"
                    })
                    await redis_pubsub.close()
                except Exception as e:
                    logger.warning(f"Failed to publish control plane output event: {e}")
                
                # Update unread count
                count = await notification_service.get_unread_count(username)
                await broadcast_unread_count_update(username, count)
            except Exception as wse:
                logger.warning(f"WebSocket broadcast failed: {wse}")
            
            return notification
        
        result = loop.run_until_complete(create_and_broadcast())
        
        logger.info(f"Created and broadcasted notification {result.id} for user {username}")
        return {
            'success': True,
            'notification_id': str(result.id),
            'username': username
        }
    except Exception as e:
        logger.error(f"Failed to create and broadcast notification: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


@celery_app.task(name='notifications.send_deployment_notification')
def send_deployment_notification(
    username: str,
    deployment_id: str,
    deployment_name: str,
    status: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Send notification for deployment completion
    """
    status_map = {
        'success': ('success', 'Deployment Completed'),
        'failed': ('error', 'Deployment Failed'),
        'in_progress': ('info', 'Deployment In Progress')
    }
    
    notif_type, title_prefix = status_map.get(status, ('info', 'Deployment Update'))
    
    title = f"{title_prefix}: {deployment_name}"
    message = f"Deployment {deployment_name} has {status}"
    
    notif_metadata = {
        'deployment_id': deployment_id,
        'deployment_name': deployment_name,
        'status': status,
        'notification_type': 'deployment', # Store explicitly
        **(metadata or {})
    }
    
    return create_and_broadcast_notification.delay(
        username=username,
        title=title,
        message=message,
        notification_type='deployment', # mapped to metadata
        priority='high' if status == 'failed' else 'normal',
        metadata=notif_metadata
    )


@celery_app.task(name='notifications.send_pdf_processing_notification')
def send_pdf_processing_notification(
    username: str,
    file_name: str,
    status: str,
    processing_result: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Send notification for PDF processing completion
    """
    if status == 'completed':
        notif_type = 'success'
        title = f"PDF Processing Completed: {file_name}"
        message = f"Your PDF file '{file_name}' has been processed successfully."
        priority = 'normal'
    else:
        notif_type = 'error'
        title = f"PDF Processing Failed: {file_name}"
        message = f"Failed to process PDF file '{file_name}'. Please try again."
        priority = 'high'
    
    notif_metadata = {
        'file_name': file_name,
        'status': status,
        'processing_result': processing_result,
        'notification_type': 'pdf_processing',
        **(metadata or {})
    }
    
    return create_and_broadcast_notification.delay(
        username=username,
        title=title,
        message=message,
        notification_type='pdf_processing',
        priority=priority,
        metadata=notif_metadata
    )


@celery_app.task(name='notifications.batch_send')
def batch_send_notifications(notifications: list):
    """
    Send multiple notifications in batch
    
    Args:
        notifications: List of notification dictionaries (must use 'username' key)
    """
    results = []
    for notif in notifications:
        # Backward compat: if user_id present but username not, map it
        if 'user_id' in notif and 'username' not in notif:
            notif['username'] = notif.pop('user_id')
            
        result = create_and_broadcast_notification.delay(**notif)
        results.append(result.id)
    
    return {
        'success': True,
        'task_ids': results,
        'count': len(notifications)
    }
