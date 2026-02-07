"""
Analytics Routes

Endpoints for analytics and metrics.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.orm.user import User
from app.auth.dependencies import get_current_active_user, require_admin
from app.services.analytics.service import AnalyticsService


router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard")
async def get_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Get dashboard metrics for current user.

    Returns user-specific analytics.
    """
    service = AnalyticsService(db)
    return await service.get_dashboard_metrics(current_user.id)


@router.get("/admin")
async def get_admin_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """
    Get admin dashboard metrics.

    Returns system-wide analytics (admin only).
    """
    service = AnalyticsService(db)
    return await service.get_admin_metrics()


@router.get("/admin/user-growth")
async def get_user_growth(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list:
    """
    Get user growth data.

    Returns daily user registration counts (admin only).
    """
    service = AnalyticsService(db)
    return await service.get_user_growth(days)


@router.get("/admin/project-activity")
async def get_project_activity(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list:
    """
    Get project activity data.

    Returns daily project creation counts (admin only).
    """
    service = AnalyticsService(db)
    return await service.get_project_activity(days)


@router.post("/track")
async def track_event(
    event_name: str,
    properties: dict = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Track analytics event.

    Tracks a custom event for the current user.
    """
    service = AnalyticsService(db)
    await service.track_event(
        event_name=event_name,
        user_id=current_user.id,
        properties=properties,
    )
    return {"status": "tracked"}
