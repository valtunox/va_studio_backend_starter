"""
Swagger Admin Configuration

Provides optional custom Swagger UI registration with authentication support.
This module can be used to add protected /swagger endpoint alongside the default /docs.
"""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing import Optional
import secrets

from app.core.settings import settings


# Optional HTTP Basic auth for Swagger (disabled by default)
security = HTTPBasic(auto_error=False)


def verify_swagger_credentials(
    credentials: Optional[HTTPBasicCredentials] = Depends(security),
) -> bool:
    """
    Verify credentials for protected Swagger access.
    Returns True if auth is disabled or credentials are valid.
    """
    # If no SWAGGER_USERNAME is set, allow public access
    swagger_user = getattr(settings, "SWAGGER_USERNAME", None)
    swagger_pass = getattr(settings, "SWAGGER_PASSWORD", None)
    
    if not swagger_user or not swagger_pass:
        return True
    
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    correct_username = secrets.compare_digest(credentials.username, swagger_user)
    correct_password = secrets.compare_digest(credentials.password, swagger_pass)
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    return True


def register_swagger_admin(app: FastAPI) -> None:
    """
    Register custom Swagger UI endpoints.
    
    This adds /swagger as an alternative to /docs with optional authentication.
    Use this when you need protected API documentation or custom branding.
    
    To enable authentication, set these environment variables:
        SWAGGER_USERNAME=admin
        SWAGGER_PASSWORD=your-secure-password
    """
    
    @app.get("/swagger", include_in_schema=False)
    async def swagger_ui(authenticated: bool = Depends(verify_swagger_credentials)):
        """Custom Swagger UI endpoint."""
        return get_swagger_ui_html(
            openapi_url=app.openapi_url or "/openapi.json",
            title=f"{app.title} - Swagger UI",
            swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
        )
    
    @app.get("/swagger/redoc", include_in_schema=False)
    async def redoc_ui(authenticated: bool = Depends(verify_swagger_credentials)):
        """Custom ReDoc endpoint."""
        return get_redoc_html(
            openapi_url=app.openapi_url or "/openapi.json",
            title=f"{app.title} - ReDoc",
            redoc_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
        )
