"""Service modules for business logic."""

from app.services.health.routes import router as health_router

__all__ = [
    "health_router",
]
