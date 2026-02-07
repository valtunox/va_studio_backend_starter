"""Analytics service."""

from app.services.analytics.routes import router
from app.services.analytics.service import AnalyticsService

__all__ = ["router", "AnalyticsService"]
