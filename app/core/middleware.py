"""
Custom Middleware

Request/response middleware for logging, timing, and monitoring.
"""

import time
from typing import Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logger import get_logger, set_correlation_id
from app.core.redis import redis_client


logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Generate correlation ID
        correlation_id = request.headers.get(
            "X-Correlation-ID",
            str(uuid4()),
        )
        set_correlation_id(correlation_id)

        # Start timer
        start_time = time.perf_counter()

        # Log request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "query": str(request.query_params),
                    "client_ip": request.client.host if request.client else None,
                }
            },
        )

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log exception
            duration = time.perf_counter() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                exc_info=True,
                extra={
                    "extra_fields": {
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": round(duration * 1000, 2),
                        "error": str(e),
                    }
                },
            )
            raise

        # Calculate duration
        duration = time.perf_counter() - start_time

        # Log response
        logger.info(
            f"Request completed: {request.method} {request.url.path}",
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                }
            },
        )

        # Add headers
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time"] = f"{duration * 1000:.2f}ms"

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        if not settings.ENABLE_RATE_LIMITING:
            return await call_next(request)

        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/healthcheck", "/"]:
            return await call_next(request)

        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"
        identifier = f"{client_ip}:{request.url.path}"

        # Check rate limit
        try:
            is_allowed, remaining = await redis_client.rate_limit_check(
                identifier,
                settings.RATE_LIMIT_REQUESTS,
                settings.RATE_LIMIT_WINDOW,
            )
        except Exception:
            # If Redis is unavailable, allow request
            return await call_next(request)

        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded for {client_ip}",
                extra={
                    "extra_fields": {
                        "client_ip": client_ip,
                        "path": request.url.path,
                    }
                },
            )
            return Response(
                content='{"detail": "Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
                headers={
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(settings.RATE_LIMIT_WINDOW),
                    "Retry-After": str(settings.RATE_LIMIT_WINDOW),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_REQUESTS)

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response
