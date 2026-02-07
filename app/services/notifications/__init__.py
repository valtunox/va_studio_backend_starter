"""Notifications service."""

from app.services.notifications.routes import router
from app.services.notifications.service import NotificationService

__all__ = ["router", "NotificationService"]
