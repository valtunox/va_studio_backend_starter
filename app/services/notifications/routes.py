"""
Notification Routes

Endpoints for notification management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.orm.user import User
from app.schemas.notification import (
    NotificationResponse,
    NotificationBulkAction,
    UnreadCountResponse,
)
from app.schemas.common import PaginatedResponse, MessageResponse
from app.auth.dependencies import get_current_active_user
from app.services.notifications.service import NotificationService


router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=PaginatedResponse[NotificationResponse])
async def list_notifications(
    page: int = 1,
    per_page: int = 20,
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    List notifications for current user.

    Returns paginated list of notifications.
    """
    service = NotificationService(db)
    skip = (page - 1) * per_page
    notifications, total = await service.get_user_notifications(
        user_id=current_user.id,
        skip=skip,
        limit=per_page,
        unread_only=unread_only,
    )

    return PaginatedResponse.create(
        items=notifications,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Get unread notification count.

    Returns the number of unread notifications.
    """
    service = NotificationService(db)
    count = await service.get_unread_count(current_user.id)

    return {"count": count}


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> NotificationResponse:
    """
    Get notification by ID.

    Returns notification details.
    """
    service = NotificationService(db)
    notification = await service.get_by_id(notification_id, current_user.id)

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return notification


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_as_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> NotificationResponse:
    """
    Mark notification as read.

    Marks the specified notification as read.
    """
    service = NotificationService(db)
    notification = await service.get_by_id(notification_id, current_user.id)

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return await service.mark_as_read(notification)


@router.post("/{notification_id}/unread", response_model=NotificationResponse)
async def mark_as_unread(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> NotificationResponse:
    """
    Mark notification as unread.

    Marks the specified notification as unread.
    """
    service = NotificationService(db)
    notification = await service.get_by_id(notification_id, current_user.id)

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return await service.mark_as_unread(notification)


@router.post("/read-all", response_model=MessageResponse)
async def mark_all_as_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Mark all notifications as read.

    Marks all notifications as read for the current user.
    """
    service = NotificationService(db)
    count = await service.mark_all_as_read(current_user.id)

    return {"message": f"Marked {count} notifications as read", "success": True}


@router.delete("/{notification_id}", response_model=MessageResponse)
async def delete_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Delete notification.

    Deletes the specified notification.
    """
    service = NotificationService(db)
    notification = await service.get_by_id(notification_id, current_user.id)

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    await service.delete(notification)

    return {"message": "Notification deleted successfully", "success": True}


@router.delete("/", response_model=MessageResponse)
async def delete_all_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Delete all notifications.

    Deletes all notifications for the current user.
    """
    service = NotificationService(db)
    count = await service.delete_all(current_user.id)

    return {"message": f"Deleted {count} notifications", "success": True}


@router.post("/bulk", response_model=MessageResponse)
async def bulk_action(
    data: NotificationBulkAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Perform bulk action on notifications.

    Supports: mark_read, mark_unread, delete
    """
    service = NotificationService(db)
    count = await service.bulk_action(
        user_id=current_user.id,
        notification_ids=data.notification_ids,
        action=data.action,
    )

    return {"message": f"Action performed on {count} notifications", "success": True}
