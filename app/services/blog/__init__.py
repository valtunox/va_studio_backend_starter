"""Blog/CMS service."""

from app.services.blog.routes import router
from app.services.blog.service import BlogService

__all__ = ["router", "BlogService"]
