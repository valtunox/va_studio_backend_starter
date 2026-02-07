"""
Health Check Routes

Endpoints for application health monitoring.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.redis import redis_client


router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict:
    """
    Basic health check.

    Returns application status.
    """
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT.value,
    }


@router.get("/health/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Readiness check.

    Checks if all dependencies (database, redis) are available.
    """
    checks = {
        "database": False,
        "redis": False,
    }

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass

    # Check Redis
    try:
        await redis_client.client.ping()
        checks["redis"] = True
    except Exception:
        pass

    all_healthy = all(checks.values())

    return {
        "status": "ready" if all_healthy else "not ready",
        "checks": checks,
        "version": settings.APP_VERSION,
    }


@router.get("/health/live")
async def liveness_check() -> dict:
    """
    Liveness check.

    Simple check to verify the application is running.
    """
    return {"status": "alive"}
