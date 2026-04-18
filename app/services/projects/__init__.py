"""Project management service."""

from app.services.projects.routes import router
from app.services.projects.service import ProjectService

__all__ = ["router", "ProjectService"]
