"""
Notifications Service Router
============================

FastAPI router providing REST API endpoints for notification management.
Includes endpoints for sending notifications, retrieving user notifications,
managing notification status, and handling user preferences.

Endpoints:
    - POST /send - Send a new notification
    - GET /user/{username} - Get user notifications
    - GET /user/{username}/unread-count - Get unread count
    - GET /{notification_id} - Get specific notification
    - PATCH /{notification_id} - Update notification (mark as read)
    - POST /user/{username}/mark-all-read - Mark all as read
    - DELETE /{notification_id} - Delete notification
    - GET /user/{username}/preferences - Get user preferences
    - PATCH /user/{username}/preferences - Update preferences
    - GET /health - Health check

All endpoints integrate with WebSocket for real-time updates.

Usage:
    from app.services.notifications.router import router
    app.include_router(router, prefix="/api/notifications", tags=["Notifications"])
"""

from app.core.logger import get_logger
import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Path, Body, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import UUID

from app.services.notifications.service import notification_service
from app.services.notifications.models import (
    NotificationCreate, NotificationRead, NotificationUpdate,
    NotificationPreferencesRead, NotificationPreferencesUpdate
)
# Import auth from main app auth module
from app.auth.auth import get_current_user, get_current_active_user

logger = get_logger(__name__)

router = APIRouter()


# Helper function to get username from authenticated user
async def get_current_username(user: Dict[str, Any] = Depends(get_current_user)) -> str:
    """Extract username from current authenticated user"""
    username = user.get("username")
    if not username:
        raise HTTPException(
            status_code=400,
            detail="User username not found in authentication token"
        )
    return username


# Request/Response models for backwards compatibility and new fields
class NotificationRequest(BaseModel):
    username: str # was user_id
    recipient: Optional[str] = None # New required field, but optional here to infer from username/email if possible
    title: str
    message: str
    notification_type: str = "info"  # info, warning, error, success
    channel_type: str = "in_app"
    priority: str = "normal"  # low, normal, high, urgent
    metadata: Optional[Dict[str, Any]] = None
    ai_generated_content_1: Optional[Dict[str, Any]] = None
    ai_generated_content_2: Optional[Dict[str, Any]] = None


class NotificationResponse(BaseModel):
    success: bool
    notification_id: str
    status: str
    timestamp: datetime


class NotificationListResponse(BaseModel):
    notifications: List[NotificationRead]
    total: int
    unread_count: int


class QueueNotificationResponse(BaseModel):
    """Response when notification is enqueued to queue pipeline."""
    queued: bool
    notification_id: str
    message: str
    timestamp: datetime


# Notification endpoints
@router.post("/send-via-queue", response_model=QueueNotificationResponse)
async def send_notification_via_queue(
    request: NotificationRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Send a notification via the queue pipeline.
    Notification is enqueued and processed for Redis/WebSocket delivery.
    """
    from datetime import datetime as dt
    from uuid import uuid4
    try:
        from app.services.queue.queue_pipeline_service import produce_notification
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Queue pipeline not available (queue service not loaded)"
        )

    username = request.username or current_user.get("username")
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    recipient = request.recipient or current_user.get("email") or username
    organization = "xcloud"
    if current_user.get("organization") and isinstance(current_user["organization"], dict):
        organization = current_user["organization"].get("name", "xcloud") or "xcloud"

    notification_id = str(uuid4())
    now = dt.utcnow()
    payload = {
        "id": notification_id,
        "username": username,
        "organization": organization,
        "recipient": recipient,
        "title": request.title,
        "body": request.message,
        "message": request.message,
        "channel_type": request.channel_type,
        "priority": request.priority,
        "type": request.notification_type,
        "data": request.metadata,
        "metadata": request.metadata,
        "created_at": now.isoformat(),
    }
    queued = await produce_notification(payload, key=notification_id)
    if not queued:
        raise HTTPException(
            status_code=503,
            detail="Failed to enqueue notification to queue pipeline (broker may be unavailable)"
        )
    return QueueNotificationResponse(
        queued=True,
        notification_id=notification_id,
        message="Notification enqueued to queue pipeline and processed for broadcast.",
        timestamp=now,
    )


@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    request: NotificationRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Send a notification.
    
    Note: For cloud managed services and operations notifications,
    the username from the authenticated user will be used if not provided in request.
    """
    import time
    start_time = time.time()
    
    try:
        logger.info("=" * 80)
        logger.info("📤 [API] POST /api/notifications/send - Received notification request")
        logger.info(f"   User: {current_user.get('username', 'unknown')}")
        logger.info(f"   Request: title='{request.title}', channel='{request.channel_type}', type='{request.notification_type}'")
        
        # Use authenticated user's username if not provided in request
        username = request.username or current_user.get("username")
        if not username:
            logger.error("   ❌ Username is required")
            raise HTTPException(status_code=400, detail="Username is required")
        
        # Infer recipient if not provided (use email from auth user or username)
        recipient = request.recipient or current_user.get("email") or username
        
        # Get organization from user if available
        organization = "xcloud"  # default
        if current_user.get("organization"):
            organization = current_user["organization"].get("name", "xcloud")
        elif current_user.get("organization_id"):
            # Could fetch organization name here if needed
            organization = "xcloud"
        
        logger.info(f"   Creating notification: username={username}, recipient={recipient}, org={organization}")
        
        notification_create = NotificationCreate(
            username=username,
            organization=organization,
            recipient=recipient,
            title=request.title,
            message=request.message,
            body=request.message,
            channel_type=request.channel_type,
            type=request.notification_type, # mapped to metadata in service
            priority=request.priority,
            metadata=request.metadata,
            ai_generated_content_1=request.ai_generated_content_1,
            ai_generated_content_2=request.ai_generated_content_2
        )
        
        notification = await notification_service.create_notification(notification_create)
        logger.info(f"   ✅ Notification created: id={notification.id}, status={notification.status}")
        
        # Send email notification (async, non-blocking)
        try:
            logger.info("   📧 Enqueueing email notification...")
            from app.services.notifications.email_service import email_service
            # Get user email from current_user
            user_email = current_user.get("email") or recipient
            
            # Format email
            email_content = email_service.format_notification_email(notification)
            
            # Send email asynchronously (don't wait for completion)
            asyncio.create_task(
                email_service.send_notification_email(
                    recipient=user_email,
                    subject=email_content['subject'],
                    body=email_content['body'],
                    html_body=email_content.get('html_body'),
                    notification=notification
                )
            )
            logger.info(f"   ✅ Email notification enqueued for {user_email}")
        except Exception as e:
            logger.warning(f"   ⚠️  Failed to send email notification: {e}")
        
        # Broadcast via WebSocket (async)
        try:
            logger.info("   📡 Broadcasting notification via WebSocket...")
            from app.services.notifications.websocket import broadcast_notification
            await broadcast_notification(notification)
            logger.info("   ✅ Notification broadcasted via WebSocket")
        except Exception as e:
            logger.warning(f"   ⚠️  Failed to broadcast notification: {e}")
        
        # Publish to Redis for cross-server sync (async)
        try:
            logger.info("   🔄 Publishing notification to Redis...")
            from app.services.notifications.redis_sync import notification_redis_sync
            await notification_redis_sync.publish_notification(notification)
            logger.info("   ✅ Notification published to Redis")
        except Exception as e:
            logger.warning(f"   ⚠️  Failed to publish notification to Redis: {e}")
        
        duration = time.time() - start_time
        response = NotificationResponse(
            success=True,
            notification_id=str(notification.id),
            status=notification.status,
            timestamp=notification.created_at
        )
        
        logger.info(f"   ✅ [API] Response sent: notification_id={response.notification_id}, duration={duration:.3f}s")
        logger.info("=" * 80)
        
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"   ❌ [API] Failed to send notification: {e}", exc_info=True)
        logger.error(f"   Duration: {duration:.3f}s")
        logger.info("=" * 80)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/me", response_model=NotificationListResponse)
async def get_my_notifications(
    status: Optional[str] = Query(None, description="Filter by status (unread, read, archived)"),
    limit: int = Query(50, ge=1, le=100, description="Number of notifications to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    import time
    start_time = time.time()
    username = current_user.get("username", "unknown")
    
    logger.info(f"📬 [API] GET /api/notifications/user/me - User: {username}, status={status}, limit={limit}, offset={offset}")
    """Get notifications for the current authenticated user."""
    try:
        username = current_user.get("username")
        if not username:
            logger.error(f"   ❌ User username not found")
            raise HTTPException(status_code=400, detail="User username not found")
        
        logger.info(f"   Fetching notifications for user: {username}")
        notifications = await notification_service.get_user_notifications(
            username=username,
            status=status,
            limit=limit,
            offset=offset
        )
        
        logger.info(f"   Fetching unread count for user: {username}")
        unread_count = await notification_service.get_unread_count(username)
        
        duration = time.time() - start_time
        response = NotificationListResponse(
            notifications=notifications,
            total=len(notifications),
            unread_count=unread_count
        )
        
        logger.info(f"   ✅ [API] Response: {len(notifications)} notifications, {unread_count} unread, duration={duration:.3f}s")
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"   ❌ [API] Failed to get user notifications: {e}", exc_info=True)
        logger.error(f"   Duration: {duration:.3f}s")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{username}", response_model=NotificationListResponse)
async def get_user_notifications(
    username: str = Path(..., description="Username"),
    status: Optional[str] = Query(None, description="Filter by status (unread, read, archived)"),
    limit: int = Query(50, ge=1, le=100, description="Number of notifications to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Get notifications for a user.
    
    Users can only access their own notifications unless they are staff/admin.
    """
    try:
        # Security: Users can only access their own notifications
        current_username = current_user.get("username")
        if current_username != username and not current_user.get("is_staff") and not current_user.get("is_superuser"):
            raise HTTPException(
                status_code=403,
                detail="You can only access your own notifications"
            )
        
        notifications = await notification_service.get_user_notifications(
            username=username,
            status=status,
            limit=limit,
            offset=offset
        )
        
        unread_count = await notification_service.get_unread_count(username)
        
        return NotificationListResponse(
            notifications=notifications,
            total=len(notifications),
            unread_count=unread_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user notifications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/me/unread-count")
async def get_my_unread_count(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get unread notification count for the current authenticated user."""
    try:
        username = current_user.get("username")
        if not username:
            raise HTTPException(status_code=400, detail="User username not found")
        
        count = await notification_service.get_unread_count(username)
        return {"username": username, "unread_count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get unread count: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{username}/unread-count")
async def get_unread_count(
    username: str = Path(..., description="Username"),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Get unread notification count for a user.
    
    Users can only access their own unread count unless they are staff/admin.
    """
    try:
        # Security: Users can only access their own unread count
        current_username = current_user.get("username")
        if current_username != username and not current_user.get("is_staff") and not current_user.get("is_superuser"):
            raise HTTPException(
                status_code=403,
                detail="You can only access your own unread count"
            )
        
        count = await notification_service.get_unread_count(username)
        return {"username": username, "unread_count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get unread count: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{notification_id}", response_model=NotificationRead)
async def get_notification(
    notification_id: UUID = Path(..., description="Notification ID"),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get a specific notification by ID for the current authenticated user."""
    try:
        username = current_user.get("username")
        if not username:
            raise HTTPException(status_code=400, detail="User username not found")
        
        notification = await notification_service.get_notification(notification_id, username)
        
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        # Security: Ensure user can only access their own notifications
        if notification.username != username and not current_user.get("is_staff") and not current_user.get("is_superuser"):
            raise HTTPException(
                status_code=403,
                detail="You can only access your own notifications"
            )
        
        return notification
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get notification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{notification_id}", response_model=NotificationRead)
async def update_notification(
    notification_id: UUID = Path(..., description="Notification ID"),
    update: NotificationUpdate = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Update a notification (mark as read/unread/archived) for the current authenticated user."""
    try:
        username = current_user.get("username")
        if not username:
            raise HTTPException(status_code=400, detail="User username not found")
        
        # First verify the notification belongs to the user
        existing_notification = await notification_service.get_notification(notification_id, username)
        if not existing_notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        # Security: Ensure user can only update their own notifications
        if existing_notification.username != username and not current_user.get("is_staff") and not current_user.get("is_superuser"):
            raise HTTPException(
                status_code=403,
                detail="You can only update your own notifications"
            )
        
        notification = await notification_service.update_notification(
            notification_id=notification_id,
            username=username,
            update=update
        )
        
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        # Broadcast unread count update
        try:
            from app.services.notifications.websocket import broadcast_unread_count_update
            count = await notification_service.get_unread_count(username)
            await broadcast_unread_count_update(username, count)
            
            # Also publish to Redis for cross-server sync
            try:
                from app.services.notifications.redis_sync import notification_redis_sync
                await notification_redis_sync.publish_unread_count_update(username, count)
            except Exception as e:
                logger.warning(f"Failed to publish unread count to Redis: {e}")
        except Exception as e:
            logger.warning(f"Failed to broadcast unread count update: {e}")
        
        return notification
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update notification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user/me/mark-all-read")
async def mark_my_all_read(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Mark all unread notifications as read for the current authenticated user."""
    try:
        username = current_user.get("username")
        if not username:
            raise HTTPException(status_code=400, detail="User username not found")
        
        count = await notification_service.mark_all_read(username)
        
        # Broadcast unread count update
        try:
            from app.services.notifications.websocket import broadcast_unread_count_update
            await broadcast_unread_count_update(username, 0)
            
            # Also publish to Redis for cross-server sync
            try:
                from app.services.notifications.redis_sync import notification_redis_sync
                await notification_redis_sync.publish_unread_count_update(username, 0)
            except Exception as e:
                logger.warning(f"Failed to publish unread count to Redis: {e}")
        except Exception as e:
            logger.warning(f"Failed to broadcast unread count update: {e}")
        
        return {
            "success": True,
            "username": username,
            "marked_count": count,
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark all as read: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user/{username}/mark-all-read")
async def mark_all_read(
    username: str = Path(..., description="Username"),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Mark all unread notifications as read for a user.
    
    Users can only mark their own notifications as read unless they are staff/admin.
    """
    try:
        # Security: Users can only mark their own notifications as read
        current_username = current_user.get("username")
        if current_username != username and not current_user.get("is_staff") and not current_user.get("is_superuser"):
            raise HTTPException(
                status_code=403,
                detail="You can only mark your own notifications as read"
            )
        
        count = await notification_service.mark_all_read(username)
        
        # Broadcast unread count update
        try:
            from app.services.notifications.websocket import broadcast_unread_count_update
            await broadcast_unread_count_update(username, 0)
            
            # Also publish to Redis for cross-server sync
            try:
                from app.services.notifications.redis_sync import notification_redis_sync
                await notification_redis_sync.publish_unread_count_update(username, 0)
            except Exception as e:
                logger.warning(f"Failed to publish unread count to Redis: {e}")
        except Exception as e:
            logger.warning(f"Failed to broadcast unread count update: {e}")
        
        return {
            "success": True,
            "username": username,
            "marked_count": count,
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark all as read: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: UUID = Path(..., description="Notification ID"),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Delete a notification for the current authenticated user."""
    try:
        username = current_user.get("username")
        if not username:
            raise HTTPException(status_code=400, detail="User username not found")
        
        # First verify the notification belongs to the user
        existing_notification = await notification_service.get_notification(notification_id, username)
        if not existing_notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        # Security: Ensure user can only delete their own notifications
        if existing_notification.username != username and not current_user.get("is_staff") and not current_user.get("is_superuser"):
            raise HTTPException(
                status_code=403,
                detail="You can only delete your own notifications"
            )
        
        deleted = await notification_service.delete_notification(notification_id, username)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        return {
            "success": True,
            "notification_id": str(notification_id),
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete notification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Notification Preferences endpoints
@router.get("/user/me/preferences", response_model=List[NotificationPreferencesRead])
async def get_my_preferences(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get notification preferences for the current authenticated user."""
    try:
        username = current_user.get("username")
        if not username:
            raise HTTPException(status_code=400, detail="User username not found")
        
        preferences = await notification_service.get_preferences(username)
        return preferences
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get preferences: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{username}/preferences", response_model=List[NotificationPreferencesRead])
async def get_preferences(
    username: str = Path(..., description="Username"),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Get notification preferences for a user.
    
    Users can only access their own preferences unless they are staff/admin.
    """
    try:
        # Security: Users can only access their own preferences
        current_username = current_user.get("username")
        if current_username != username and not current_user.get("is_staff") and not current_user.get("is_superuser"):
            raise HTTPException(
                status_code=403,
                detail="You can only access your own preferences"
            )
        
        preferences = await notification_service.get_preferences(username)
        return preferences
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get preferences: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/user/me/preferences", response_model=List[NotificationPreferencesRead])
async def update_my_preferences(
    update: NotificationPreferencesUpdate = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Update notification preferences for the current authenticated user."""
    try:
        username = current_user.get("username")
        if not username:
            raise HTTPException(status_code=400, detail="User username not found")
        
        preferences = await notification_service.update_preferences(username, update)
        return preferences
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update preferences: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/user/{username}/preferences", response_model=List[NotificationPreferencesRead])
async def update_preferences(
    username: str = Path(..., description="Username"),
    update: NotificationPreferencesUpdate = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Update notification preferences for a user.
    
    Users can only update their own preferences unless they are staff/admin.
    """
    try:
        # Security: Users can only update their own preferences
        current_username = current_user.get("username")
        if current_username != username and not current_user.get("is_staff") and not current_user.get("is_superuser"):
            raise HTTPException(
                status_code=403,
                detail="You can only update your own preferences"
            )
        
        preferences = await notification_service.update_preferences(username, update)
        return preferences
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update preferences: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check for notifications service."""
    return {
        "status": "healthy",
        "service": "notifications",
        "timestamp": datetime.now().isoformat()
    }
