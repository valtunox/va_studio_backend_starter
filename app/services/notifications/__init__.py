"""
Notifications Service Package
==============================

Real-time notification service with WebSocket support, database persistence,
and event-driven architecture for the InfinityAI Platform.

Features:
    - REST API for notification management
    - WebSocket real-time delivery via Socket.IO
    - PostgreSQL persistence
    - Celery background task processing
    - Event-driven notification triggers
    - User preferences management
    - Multi-channel support (in-app, email, SMS, push)

Usage:
    from app.services.notifications import router, notification_service
    app.include_router(router, prefix="/api/notifications")
"""

__version__ = "1.0.0"
