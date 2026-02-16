# Notifications Service

> **A production-ready, real-time notification system with WebSocket support, PostgreSQL persistence, and event-driven architecture.**

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Features](#features)
4. [Directory Structure](#directory-structure)
5. [API Reference](#api-reference)
6. [WebSocket Events](#websocket-events)
7. [Installation & Setup](#installation--setup)
8. [Usage Examples](#usage-examples)
9. [Configuration](#configuration)
10. [Development Guide](#development-guide)

---

## Overview

The Notifications Service provides a comprehensive notification system for the InfinityAI Platform. It supports multiple notification channels, real-time delivery via WebSocket, database persistence, and event-driven triggers for system events.

### Key Capabilities

- **Real-time delivery** via Socket.IO WebSocket
- **Multi-channel support** (in-app, email, SMS, push)
- **PostgreSQL persistence** with full CRUD operations
- **Event-driven architecture** for system event notifications
- **Celery background processing** for async operations
- **User preferences** management
- **Unread count tracking** with real-time updates
- **Redis adapter** for horizontal scaling
- **AI-ready fields** for future extensibility

---

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client Apps   │    │   Load Balancer │    │   FastAPI API   │
│                 │◄──►│                 │◄──►│                 │
│ Web/Mobile/etc  │    │     (Nginx)     │    │   REST + WS     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                       ┌─────────────────┐             │
                       │  Socket.IO WS   │◄────────────┤
                       │   (Redis Adapter)│             │
                       └─────────────────┘             │
                                                        │
┌─────────────────┐    ┌─────────────────┐             │
│  System Events  │    │  Celery Workers │◄────────────┤
│                 │───►│                 │             │
│ • Deployments   │    │ • Notification  │             │
│ • PDF Processing│   │   Creation      │             │
│ • AI Agents     │    │ • Broadcasting  │             │
└─────────────────┘    └─────────────────┘             │
                                                        │
                       ┌─────────────────┐             │
                       │   PostgreSQL    │◄────────────┘
                       │                 │
                       │ • Notifications │
                       │ • Preferences   │
                       │ • Metadata      │
                       └─────────────────┘
```

### Component Flow

1. **Event Trigger**: System events (deployment, PDF processing, etc.) trigger notification creation
2. **Celery Task**: Background task creates notification in database
3. **WebSocket Broadcast**: Notification is broadcast to connected clients via Socket.IO
4. **Real-time Delivery**: Clients receive notification instantly if connected
5. **Persistence**: All notifications are stored in PostgreSQL for history

---

## Features

### ✅ Core Notification Features
- [x] Create, read, update, delete notifications
- [x] User-scoped notification queries
- [x] Status tracking (queued, sent, delivered, read, failed)
- [x] Priority levels (low, normal, high, urgent)
- [x] Scheduled notifications
- [x] Retry mechanism with configurable max retries
- [x] Error tracking and logging

### ✅ Real-time Features
- [x] WebSocket delivery via Socket.IO
- [x] Real-time unread count updates
- [x] Connection management
- [x] Multi-instance support with Redis adapter
- [x] User-based rooms for targeted delivery

### ✅ User Management
- [x] Notification preferences per user
- [x] Channel-specific preferences
- [x] Mark as read/unread
- [x] Mark all as read
- [x] Notification history

### ✅ Event Integration
- [x] Deployment completion notifications
- [x] PDF processing notifications
- [x] AI agent event notifications
- [x] Custom notification triggers
- [x] Event bus pattern

### ✅ Scalability & Performance
- [x] Redis adapter for horizontal scaling
- [x] Celery for async processing
- [x] Database connection pooling
- [x] Efficient querying with indexes
- [x] Background task processing

---

## Directory Structure

```
notifications/
├── __init__.py              # Package initialization
├── models.py                 # SQLAlchemy models and Pydantic schemas
├── service.py                # Core business logic (CRUD operations)
├── router.py                 # FastAPI REST API endpoints
├── websocket.py              # Socket.IO WebSocket server
├── tasks.py                  # Celery background tasks
├── events.py                 # Event handlers and event bus
├── schema.sql                # Database schema (if separate)
├── example_usage.py          # Usage examples
├── tests.py                  # Unit tests
└── README.md                 # This documentation
```

### File Roles

- **`models.py`**: SQLAlchemy ORM models, Pydantic schemas, database utilities
- **`service.py`**: Core business logic layer, database operations abstraction
- **`router.py`**: FastAPI REST API endpoints, request/response handling
- **`websocket.py`**: Socket.IO server, real-time delivery, connection management
- **`tasks.py`**: Celery background tasks for async notification processing
- **`events.py`**: Event bus pattern, system event handlers, convenience functions

---

## API Reference

### REST Endpoints

All endpoints are prefixed with `/api/notifications` (configurable).

#### Send Notification

**POST** `/send`

Create and send a new notification.

```json
{
  "username": "user123",
  "recipient": "user@example.com",
  "title": "Deployment Complete",
  "message": "Your deployment has completed successfully",
  "notification_type": "success",
  "channel_type": "in_app",
  "priority": "normal",
  "metadata": {
    "deployment_id": "deploy_456"
  }
}
```

**Response:**
```json
{
  "success": true,
  "notification_id": "uuid-here",
  "status": "queued",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

#### Get User Notifications

**GET** `/user/{username}`

Get notifications for a user with optional filtering.

**Query Parameters:**
- `status` (optional): Filter by status (unread, read, archived)
- `limit` (default: 50): Number of notifications to return
- `offset` (default: 0): Pagination offset

**Response:**
```json
{
  "notifications": [
    {
      "id": "uuid",
      "username": "user123",
      "title": "Deployment Complete",
      "body": "Your deployment has completed",
      "status": "unread",
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "total": 10,
  "unread_count": 5
}
```

#### Get Unread Count

**GET** `/user/{username}/unread-count`

Get unread notification count for a user.

**Response:**
```json
{
  "username": "user123",
  "unread_count": 5
}
```

#### Get Notification

**GET** `/{notification_id}?username={username}`

Get a specific notification by ID.

#### Update Notification

**PATCH** `/{notification_id}?username={username}`

Update notification (mark as read/unread/archived).

```json
{
  "status": "read",
  "read_at": "2025-01-15T10:35:00Z"
}
```

#### Mark All as Read

**POST** `/user/{username}/mark-all-read`

Mark all unread notifications as read for a user.

#### Delete Notification

**DELETE** `/{notification_id}?username={username}`

Delete a notification.

#### Get Preferences

**GET** `/user/{username}/preferences`

Get notification preferences for a user.

#### Update Preferences

**PATCH** `/user/{username}/preferences`

Update notification preferences.

```json
{
  "enabled": true
}
```

#### Health Check

**GET** `/health`

Service health check endpoint.

---

## WebSocket Events

### Connection

Connect using Socket.IO client:

```javascript
import socketio from 'socket.io-client';

const sio = socketio('http://localhost:8484', {
  auth: { username: 'user123' }
});
```

### Client Events

#### Get Unread Count

```javascript
sio.emit('get_unread_count');
```

### Server Events

#### Connected

Emitted when client successfully connects.

```json
{
  "status": "connected",
  "username": "user123"
}
```

#### New Notification

Emitted when a new notification is created for the user.

```json
{
  "id": "uuid",
  "username": "user123",
  "title": "Deployment Complete",
  "body": "Your deployment has completed",
  "status": "queued",
  "created_at": "2025-01-15T10:30:00Z"
}
```

#### Unread Count Update

Emitted when unread count changes.

```json
{
  "count": 5,
  "username": "user123"
}
```

#### Error

Emitted on errors.

```json
{
  "message": "Error description"
}
```

---

## Installation & Setup

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Redis 6+ (for Celery and WebSocket scaling)
- Celery worker process

### Dependencies

```bash
pip install fastapi uvicorn
pip install asyncpg sqlalchemy
pip install python-socketio[asyncio-redis]
pip install celery redis
pip install pydantic
```

### Database Setup

1. Create PostgreSQL database:
```sql
CREATE DATABASE llm_ai_lab;
```

2. Run schema (if separate schema file exists):
```bash
psql -d llm_ai_lab -f schema.sql
```

3. Or use the `create_notification_tables()` function:
```python
from app.services.notifications.models import create_notification_tables
await create_notification_tables()
```

### Redis Setup

Install and start Redis:
```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis-server

# macOS
brew install redis
brew services start redis
```

### Celery Worker

Start Celery worker for background tasks:
```bash
celery -A app.core.celery_app worker --loglevel=info
```

---

## Usage Examples

### Python - Send Notification

```python
from app.services.notifications.service import notification_service
from app.services.notifications.models import NotificationCreate

notification = NotificationCreate(
    username="user123",
    recipient="user@example.com",
    title="Hello",
    body="World",
    channel_type="in_app",
    priority="normal"
)

result = await notification_service.create_notification(notification)
print(f"Created notification: {result.id}")
```

### Python - Event-Driven Notification

```python
from app.services.notifications.events import notify_deployment_complete

await notify_deployment_complete(
    username="user123",
    deployment_id="deploy_456",
    deployment_name="My Deployment",
    status="success"
)
```

### JavaScript - WebSocket Client

```javascript
import socketio from 'socket.io-client';

const sio = socketio('http://localhost:8484', {
  auth: { username: 'user123' }
});

sio.on('connect', () => {
  console.log('Connected to notifications');
});

sio.on('new_notification', (notification) => {
  console.log('New notification:', notification);
  // Display notification in UI
});

sio.on('unread_count_update', (data) => {
  console.log('Unread count:', data.count);
  // Update badge in UI
});
```

### REST API - Send Notification

```bash
curl -X POST http://localhost:8484/api/notifications/send \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user123",
    "title": "Hello",
    "message": "World",
    "channel_type": "in_app"
  }'
```

---

## Configuration

### Environment Variables

```bash
# Database
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=llm_ai_lab
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# WebSocket
WEBSOCKET_CORS_ORIGINS=*
```

### Database Schema

Key tables:
- `notifications`: Main notifications table
- `notification_preferences`: User notification preferences

See `models.py` for full schema details.

---

## Development Guide

### Running in Development

```bash
# Start FastAPI server
uvicorn app.app:app --reload --port 8484

# Start Celery worker (separate terminal)
celery -A app.core.celery_app worker --loglevel=info

# Start Redis (if not running)
redis-server
```

### Testing

```bash
# Unit tests
python -m pytest app/services/notifications/tests.py

# Integration tests
python -m pytest tests/integration/
```

### Code Structure

- **Models**: Database models and schemas
- **Service**: Business logic layer
- **Router**: API endpoints
- **WebSocket**: Real-time delivery
- **Tasks**: Background processing
- **Events**: Event handlers

### Adding New Notification Types

1. Add event handler in `events.py`:
```python
async def notify_custom_event(username: str, data: dict):
    await notification_event_bus.send_custom_notification(
        username=username,
        title="Custom Event",
        message="Event description",
        notification_type="info",
        metadata=data
    )
```

2. Trigger from your service:
```python
from app.services.notifications.events import notify_custom_event
await notify_custom_event("user123", {"event_id": "123"})
```

---

## Architecture Decisions

### Why Socket.IO?

- Built-in room support for user-based delivery
- Redis adapter for multi-instance scaling
- Automatic reconnection handling
- Cross-platform compatibility

### Why Celery?

- Async processing for non-blocking operations
- Retry mechanism for failed notifications
- Scalable worker pool
- Integration with existing infrastructure

### Why PostgreSQL?

- ACID compliance for reliable persistence
- JSONB support for flexible metadata
- Full-text search capabilities
- Mature ecosystem

---

## Future Enhancements

- [ ] Email channel implementation
- [ ] SMS channel implementation
- [ ] Push notification support (FCM, APNS)
- [ ] Notification templates
- [ ] Rich notification content (images, actions)
- [ ] Notification grouping
- [ ] Delivery receipts
- [ ] Analytics and metrics
- [ ] Rate limiting
- [ ] Notification scheduling UI

---

**Last Updated**: January 2025  
**Version**: 1.0.0  
**License**: Proprietary - InfinityAI Platform
