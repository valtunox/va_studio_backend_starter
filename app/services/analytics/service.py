"""
Analytics Service

Event tracking and metrics collection.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_client
from app.core.logger import get_logger
from app.orm.user import User
from app.orm.project import Project


logger = get_logger(__name__)


class AnalyticsService:
    """Analytics service for event tracking and metrics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # Event tracking
    async def track_event(
        self,
        event_name: str,
        user_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track an analytics event.

        Args:
            event_name: Name of the event
            user_id: Optional user ID
            properties: Optional event properties
        """
        event_data = {
            "event": event_name,
            "user_id": user_id,
            "properties": properties or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Store in Redis for real-time analytics
        try:
            key = f"analytics:events:{datetime.now().strftime('%Y%m%d')}"
            await redis_client.client.lpush(key, str(event_data))
            await redis_client.client.expire(key, 86400 * 7)  # Keep for 7 days
        except Exception as e:
            logger.warning(f"Failed to store analytics event: {e}")

        # Increment event counter
        try:
            counter_key = f"analytics:count:{event_name}"
            await redis_client.incr(counter_key)
        except Exception:
            pass

    async def track_page_view(
        self,
        path: str,
        user_id: Optional[str] = None,
        referrer: Optional[str] = None,
    ) -> None:
        """Track page view."""
        await self.track_event(
            "page_view",
            user_id=user_id,
            properties={"path": path, "referrer": referrer},
        )

    async def track_user_action(
        self,
        action: str,
        user_id: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ) -> None:
        """Track user action."""
        await self.track_event(
            f"user_{action}",
            user_id=user_id,
            properties={
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        )

    # Dashboard metrics
    async def get_dashboard_metrics(self, user_id: str) -> Dict[str, Any]:
        """Get dashboard metrics for user."""
        # Get user's project count
        project_count = await self.db.scalar(
            select(func.count()).where(
                Project.owner_id == user_id,
                Project.is_deleted == False,
            )
        )

        # Get active projects
        active_projects = await self.db.scalar(
            select(func.count()).where(
                Project.owner_id == user_id,
                Project.is_deleted == False,
                Project.status == "active",
            )
        )

        return {
            "total_projects": project_count or 0,
            "active_projects": active_projects or 0,
            "storage_used_mb": 0,  # Placeholder
            "api_calls_this_month": 0,  # Placeholder
        }

    async def get_admin_metrics(self) -> Dict[str, Any]:
        """Get admin dashboard metrics."""
        # Total users
        total_users = await self.db.scalar(
            select(func.count()).where(User.is_deleted == False)
        )

        # Active users (last 7 days)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        active_users = await self.db.scalar(
            select(func.count()).where(
                User.is_deleted == False,
                User.updated_at >= week_ago,
            )
        )

        # Total projects
        total_projects = await self.db.scalar(
            select(func.count()).where(Project.is_deleted == False)
        )

        # New users today
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        new_users_today = await self.db.scalar(
            select(func.count()).where(
                User.is_deleted == False,
                User.created_at >= today_start,
            )
        )

        return {
            "total_users": total_users or 0,
            "active_users": active_users or 0,
            "total_projects": total_projects or 0,
            "new_users_today": new_users_today or 0,
        }

    async def get_user_growth(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get user growth data for the last N days."""
        data = []
        today = datetime.now(timezone.utc).date()

        for i in range(days - 1, -1, -1):
            date = today - timedelta(days=i)
            start = datetime.combine(date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end = start + timedelta(days=1)

            count = await self.db.scalar(
                select(func.count()).where(
                    User.is_deleted == False,
                    User.created_at >= start,
                    User.created_at < end,
                )
            )

            data.append({
                "date": date.isoformat(),
                "count": count or 0,
            })

        return data

    async def get_project_activity(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get project activity for the last N days."""
        data = []
        today = datetime.now(timezone.utc).date()

        for i in range(days - 1, -1, -1):
            date = today - timedelta(days=i)
            start = datetime.combine(date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end = start + timedelta(days=1)

            count = await self.db.scalar(
                select(func.count()).where(
                    Project.is_deleted == False,
                    Project.created_at >= start,
                    Project.created_at < end,
                )
            )

            data.append({
                "date": date.isoformat(),
                "count": count or 0,
            })

        return data
