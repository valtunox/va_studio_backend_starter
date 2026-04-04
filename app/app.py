"""
VA Studio Backend - Main Application

A production-ready FastAPI backend with a public-first architecture.
Templates, chat, and health endpoints are always available without auth.
Auth, billing, and protected services activate when users sign up.
"""

import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# Running this file directly (python app/app.py) puts app/ on sys.path first.
# Add project root so absolute imports resolve to the app package.
if __package__ in (None, ""):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.settings import settings
from app.core.db import init_db, close_db
from app.core.redis import redis_client
from app.core.logger import get_logger
from app.core.middleware import (
    RequestLoggingMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.orm.base import Base

from app.templates.service_loader import get_service_loader, ServiceLoader
from app.templates.registry import TemplateType

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.

    On every startup (including hot-reload), this:
      1. Runs migration.py — discovers ORM models, creates tables, adds columns
      2. Initializes async DB engine + connection pool
      3. Connects Redis

    This is the core of the low-code/vibe-coding workflow:
      AI or user adds/modifies models in app/orm/ → app reloads →
      migration picks up changes → DB schema is synced automatically.
    """
    # Get service loader
    service_loader = get_service_loader()
    template_info = service_loader.get_template_info()

    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT.value}")
    logger.info(f"Template: {template_info['name']} ({template_info['type']})")
    logger.info(f"Enabled services: {', '.join(template_info.get('loaded_services', template_info.get('required_services', [])))}")

    # ── Run migration on every startup/reload ──
    # This discovers all ORM models in app/orm/, creates missing tables,
    # and adds missing columns. Safe and additive-only.
    try:
        from migration import run_migration
        result = run_migration()
        if result["success"]:
            logger.info(
                f"Migration OK — {result['tables_total']} tables, "
                f"{result['tables_created']} created, "
                f"{result['columns_added']} columns added"
            )
        else:
            logger.warning("Migration completed with errors — check logs above")
    except Exception as e:
        logger.error(f"Migration failed: {e}")

    # Initialize async database engine + connection pool
    try:
        await init_db()
        table_names = sorted(Base.metadata.tables.keys())
        logger.info(f"Async DB engine ready — {len(table_names)} tables: {table_names}")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    # Initialize Redis (always needed for public chat sessions + caching)
    try:
        await redis_client.connect()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Redis connection failed (chat sessions will be unavailable): {e}")

    # Initialize Celery (if required)
    if service_loader.requires_celery():
        logger.info("Celery worker integration enabled")

    yield

    # Shutdown
    logger.info("Shutting down application...")

    # Close Redis
    try:
        await redis_client.disconnect()
        logger.info("Redis disconnected")
    except Exception:
        pass

    # Close database
    try:
        await close_db()
        logger.info("Database connections closed")
    except Exception:
        pass

    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
    lifespan=lifespan,
)


# Add CORS middleware
if settings.ENABLE_CORS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )


# Add custom middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)

if settings.ENABLE_RATE_LIMITING:
    app.add_middleware(RateLimitMiddleware)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.DEBUG else "An error occurred",
        },
    )


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information and public endpoints."""
    service_loader = get_service_loader()
    template_info = service_loader.get_template_info()
    
    response = {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": settings.APP_DESCRIPTION,
        "architecture": "public-first",
        "template": {
            "type": template_info["type"],
            "name": template_info["name"],
            "description": template_info["description"],
        },
        "public_endpoints": {
            "health": "/health",
            "templates": f"{settings.API_V1_PREFIX}/templates/",
            "chat_session": f"{settings.API_V1_PREFIX}/chat/session",
            "chat_message": f"{settings.API_V1_PREFIX}/chat/message",
            "template_request": f"{settings.API_V1_PREFIX}/chat/template-request",
        },
        "docs": "/docs" if settings.ENABLE_DOCS else None,
        "features": template_info["feature_flags"],
    }
    
    if settings.DEBUG:
        response["debug_info"] = {
            "loaded_services": template_info.get("loaded_services", []),
            "public_services": service_loader.PUBLIC_SERVICES,
            "requires_redis": template_info["requires_redis"],
            "requires_celery": template_info["requires_celery"],
            "requires_billing": template_info["requires_billing"],
        }
    
    return response


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint - always public, no auth required."""
    health = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT.value,
    }

    # Check Redis connectivity
    try:
        if redis_client._client:
            await redis_client._client.ping()
            health["redis"] = "connected"
        else:
            health["redis"] = "not configured"
    except Exception:
        health["redis"] = "disconnected"

    return health


# Database introspection endpoint (for vibe coding / AI builder feedback)
@app.get("/db/tables", tags=["Database"])
async def list_db_tables():
    """List all ORM-registered tables and their columns."""
    tables_info = {}
    for table_name, table in sorted(Base.metadata.tables.items()):
        tables_info[table_name] = {
            "columns": [
                {
                    "name": col.name,
                    "type": str(col.type),
                    "nullable": col.nullable,
                    "primary_key": col.primary_key,
                }
                for col in table.columns
            ],
            "column_count": len(table.columns),
        }
    return {
        "table_count": len(tables_info),
        "tables": tables_info,
    }


# Get service loader and load required routers
service_loader = get_service_loader()
routers = service_loader.load_required_routers()

# Include routers dynamically
for service_name, router in routers.items():
    app.include_router(router, prefix=settings.API_V1_PREFIX)
    logger.debug(f"Included router: {service_name}")

logger.info(f"Loaded {len(routers)} service routers for template: {service_loader.get_template_type().value}")

# Register custom Swagger admin endpoints (/swagger, /swagger/redoc)
try:
    from app.auth.admin import register_swagger_admin
    register_swagger_admin(app)
    logger.debug("Custom Swagger admin endpoints registered at /swagger")
except ImportError:
    pass


# Application entry point
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        reload_dirs=["app", "."] if settings.RELOAD else None,
        workers=1 if settings.RELOAD else settings.WORKERS,
    )
