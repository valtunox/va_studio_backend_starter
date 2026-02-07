"""
Notification Service

Business logic for in-app notifications.
"""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.orm.notification import Notification, NotificationType
from app.schemas.notification import NotificationCreate


class NotificationService:
    """Notification service for CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(
        self,
        notification_id: str,
        user_id: str,
    ) -> Optional[Notification]:
        """Get notification by ID for user."""
        result = await self.db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_notifications(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        unread_only: bool = False,
    ) -> tuple[List[Notification], int]:
        """Get notifications for user with pagination."""
        query = select(Notification).where(Notification.user_id == user_id)

        if unread_only:
            query = query.where(Notification.is_read == False)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        # Get paginated results
        query = query.offset(skip).limit(limit).order_by(Notification.created_at.desc())
        result = await self.db.execute(query)
        notifications = list(result.scalars().all())

        return notifications, total

    async def get_unread_count(self, user_id: str) -> int:
        """Get unread notification count for user."""
        result = await self.db.execute(
            select(func.count()).where(
                Notification.user_id == user_id,
                Notification.is_read == False,
            )
        )
        return result.scalar() or 0

    async def create(
        self,
        user_id: str,
        notification_data: NotificationCreate,
    ) -> Notification:
        """Create notification for user."""
        notification = Notification(
            user_id=user_id,
            title=notification_data.title,
            message=notification_data.message,
            type=notification_data.type,
            action_url=notification_data.action_url,
            action_label=notification_data.action_label,
            reference_type=notification_data.reference_type,
            reference_id=notification_data.reference_id,
            metadata_=notification_data.metadata,
        )

        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)

        return notification

    async def create_system_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        action_url: Optional[str] = None,
    ) -> Notification:
        """Create system notification."""
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=NotificationType.SYSTEM.value,
            action_url=action_url,
        )

        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)

        return notification

    async def mark_as_read(self, notification: Notification) -> Notification:
        """Mark notification as read."""
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(notification)

        return notification

    async def mark_as_unread(self, notification: Notification) -> Notification:
        """Mark notification as unread."""
        notification.is_read = False
        notification.read_at = None

        await self.db.commit()
        await self.db.refresh(notification)

        return notification

    async def mark_all_as_read(self, user_id: str) -> int:
        """Mark all notifications as read for user."""
        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read == False,
            )
            .values(is_read=True, read_at=now)
        )

        await self.db.commit()
        return result.rowcount

    async def delete(self, notification: Notification) -> None:
        """Delete notification."""
        await self.db.delete(notification)
        await self.db.commit()

    async def delete_all(self, user_id: str) -> int:
        """Delete all notifications for user."""
        result = await self.db.execute(
            select(Notification).where(Notification.user_id == user_id)
        )
        notifications = result.scalars().all()

        count = len(notifications)
        for notification in notifications:
            await self.db.delete(notification)

        await self.db.commit()
        return count

    async def bulk_action(
        self,
        user_id: str,
        notification_ids: List[str],
        action: str,
    ) -> int:
        """Perform bulk action on notifications."""
        if action == "mark_read":
            now = datetime.now(timezone.utc)
            result = await self.db.execute(
                update(Notification)
                .where(
                    Notification.user_id == user_id,
                    Notification.id.in_(notification_ids),
                )
                .values(is_read=True, read_at=now)
            )
            await self.db.commit()
            return result.rowcount

        elif action == "mark_unread":
            result = await self.db.execute(
                update(Notification)
                .where(
                    Notification.user_id == user_id,
                    Notification.id.in_(notification_ids),
                )
                .values(is_read=False, read_at=None)
            )
            await self.db.commit()
            return result.rowcount

        elif action == "delete":
            result = await self.db.execute(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.id.in_(notification_ids),
                )
            )
            notifications = result.scalars().all()
            count = len(notifications)
            for notification in notifications:
                await self.db.delete(notification)
            await self.db.commit()
            return count

        return 0
