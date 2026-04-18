"""User management service."""

from app.services.users.routes import router
from app.services.users.service import UserService

__all__ = ["router", "UserService"]
