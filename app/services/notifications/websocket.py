"""
WebSocket Server for Real-Time Notifications
=============================================

This module provides a Socket.IO WebSocket server for real-time notification
delivery. It includes connection management, room-based broadcasting, and
Redis adapter support for horizontal scaling across multiple instances.

Features:
    - Socket.IO async server
    - User-based rooms for targeted delivery
    - Redis adapter for multi-instance support
    - Connection tracking
    - Real-time unread count updates
    - Automatic session management

Events:
    - connect: Client connection handler
    - disconnect: Client disconnection handler
    - get_unread_count: Request unread count
    - new_notification: Broadcast new notification
    - unread_count_update: Broadcast unread count change

Usage:
    The socket_app is automatically mounted in the main FastAPI application.
    Clients connect using Socket.IO client library:
    
    import socketio
    sio = socketio.Client()
    sio.connect('http://localhost:8484', auth={'username': 'user123'})
    sio.on('new_notification', handle_notification)
"""

import os
from app.core.logger import get_logger
import json
from typing import Dict, Any, Optional
import socketio
from fastapi import FastAPI
from app.services.notifications.service import notification_service
from app.services.notifications.models import NotificationRead
# Import auth utilities
from app.auth.auth import decode_token

logger = get_logger(__name__)

# Get Redis URL from environment
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=os.getenv('WEBSOCKET_CORS_ORIGINS', '*').split(',') if os.getenv('WEBSOCKET_CORS_ORIGINS') != '*' else '*',
    logger=False,
    engineio_logger=False
)

# Create Socket.IO app
socket_app = socketio.ASGIApp(sio)

# Track connected users (username -> set of session_ids)
connected_users: Dict[str, set] = {}


@sio.event
async def connect(sid, environ, auth):
    """
    Handle client connection with JWT token authentication
    
    Args:
        sid: Session ID
        environ: Environment dictionary
        auth: Authentication data (should contain 'token' with JWT)
    """
    try:
        username = None
        user_id = None
        
        # Primary method: Extract JWT token from auth dict
        if auth and isinstance(auth, dict):
            token = auth.get('token') or auth.get('access_token')
            if token:
                # Decode and validate JWT token
                payload = decode_token(token)
                if payload:
                    user_id = payload.get('user_id')
                    username = payload.get('username')
                    # If username not in token, try to get from auth dict or email
                    if not username:
                        username = auth.get('username')  # Check auth dict first
                    if not username and payload.get('email'):
                        # Extract from email as fallback
                        email = payload.get('email')
                        username = email.split('@')[0] if email else None
                    # Last resort: try to get from database
                    if not username and user_id:
                        try:
                            from app.auth.auth import auth_db
                            user = auth_db.get_user_by_id(user_id)
                            if user:
                                username = user.get('username')
                        except Exception as e:
                            logger.warning(f"Could not fetch username from DB: {e}")
        
        # Fallback: Try query string for token
        if not username:
            query_string = environ.get('QUERY_STRING', '')
            if 'token=' in query_string:
                token = query_string.split('token=')[1].split('&')[0]
                payload = decode_token(token)
                if payload:
                    user_id = payload.get('user_id')
                    username = payload.get('username')
                    if not username and payload.get('email'):
                        email = payload.get('email')
                        username = email.split('@')[0] if email else None
                    # Try to get from database if still not found
                    if not username and user_id:
                        try:
                            from app.auth.auth import auth_db
                            user = auth_db.get_user_by_id(user_id)
                            if user:
                                username = user.get('username')
                        except Exception as e:
                            logger.warning(f"Could not fetch username from DB: {e}")
        
        # Legacy fallback: Direct username/user_id in auth or query (for backward compatibility)
        if not username:
            if auth and isinstance(auth, dict):
                username = auth.get('username') or auth.get('user_id')
            
            if not username:
                query_string = environ.get('QUERY_STRING', '')
                if 'username=' in query_string:
                    username = query_string.split('username=')[1].split('&')[0]
                elif 'user_id=' in query_string:
                    username = query_string.split('user_id=')[1].split('&')[0]
        
        if not username:
            logger.warning(f"Connection rejected: No valid authentication for session {sid}")
            await sio.emit('error', {'message': 'Authentication required'}, room=sid)
            return False
        
        # Store username and user_id in session
        await sio.save_session(sid, {
            'username': username,
            'user_id': user_id
        })
        
        # Join user's room
        room = f"user_{username}"
        await sio.enter_room(sid, room)
        
        # Track connection
        if username not in connected_users:
            connected_users[username] = set()
        connected_users[username].add(sid)
        
        logger.info(f"User {username} (user_id: {user_id}) connected (session: {sid}, room: {room})")
        
        # Send connection confirmation
        await sio.emit('connected', {
            'status': 'connected',
            'username': username,
            'user_id': user_id
        }, room=sid)
        
        return True
    except Exception as e:
        logger.error(f"Connection error: {e}", exc_info=True)
        await sio.emit('error', {'message': 'Connection failed'}, room=sid)
        return False


@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    try:
        session = await sio.get_session(sid)
        username = session.get('username')
        
        if username:
            room = f"user_{username}"
            await sio.leave_room(sid, room)
            
            # Remove from tracking
            if username in connected_users:
                connected_users[username].discard(sid)
                if not connected_users[username]:
                    del connected_users[username]
            
            logger.info(f"User {username} disconnected (session: {sid})")
    except Exception as e:
        logger.error(f"Disconnection error: {e}", exc_info=True)


@sio.event
async def get_unread_count(sid):
    """Get unread notification count for the connected user"""
    try:
        session = await sio.get_session(sid)
        username = session.get('username')
        
        if not username:
            await sio.emit('error', {'message': 'User not authenticated'}, room=sid)
            return
        
        count = await notification_service.get_unread_count(username)
        await sio.emit('unread_count', {'count': count}, room=sid)
    except Exception as e:
        logger.error(f"Error getting unread count: {e}", exc_info=True)
        await sio.emit('error', {'message': str(e)}, room=sid)


async def broadcast_notification(notification: NotificationRead):
    """
    Broadcast notification to a specific user via WebSocket
    
    This function is called both:
    1. Directly when notification is created on this server
    2. From Redis pub/sub when notification is created on another server
    
    Args:
        notification: NotificationRead object to broadcast
    """
    try:
        room = f"user_{notification.username}"
        
        # Convert Pydantic model to dict
        # NotificationRead has 'username' (was user_id)
        # We'll include both new and old fields if helpful, but frontend should adapt.
        
        notification_dict = notification.model_dump()
        # Ensure dates are isoformat
        if notification.created_at:
            notification_dict['created_at'] = notification.created_at.isoformat()
        if notification.sent_at:
             notification_dict['sent_at'] = notification.sent_at.isoformat()
        if notification.read_at:
            notification_dict['read_at'] = notification.read_at.isoformat()
        
        # Add user_id alias for back compat
        notification_dict['user_id'] = notification.username
        
        await sio.emit('new_notification', notification_dict, room=room)
        logger.info(f"Broadcasted notification {notification.id} to user {notification.username} via WebSocket")
    except Exception as e:
        logger.error(f"Error broadcasting notification: {e}", exc_info=True)


async def broadcast_unread_count_update(username: str, count: int):
    """
    Broadcast unread count update to a user
    
    Args:
        username: Username
        count: New unread count
    """
    try:
        room = f"user_{username}"
        await sio.emit('unread_count_update', {'count': count, 'username': username}, room=room)
    except Exception as e:
        logger.error(f"Error broadcasting unread count update: {e}", exc_info=True)


def get_connected_users_count() -> int:
    """Get total number of connected users"""
    return len(connected_users)


def get_user_connection_count(username: str) -> int:
    """Get number of active connections for a user"""
    return len(connected_users.get(username, set()))


# Initialize Redis adapter if available
try:
    import socketio.asyncio_redis
    
    # Try to create Redis adapter for multi-instance support
    try:
        redis_adapter = socketio.asyncio_redis.RedisManager(REDIS_URL)
        sio.adapter(redis_adapter)
        logger.info(f"Redis adapter initialized for WebSocket server at {REDIS_URL}")
    except Exception as e:
        logger.warning(f"Could not initialize Redis adapter: {e}. Running in single-instance mode.")
        logger.warning("For multi-instance support, install python-socketio[asyncio-redis] or ensure Redis is available")
except ImportError:
    logger.warning("python-socketio[asyncio-redis] not installed. Running in single-instance mode.")
    logger.warning("For multi-instance support, install: pip install 'python-socketio[asyncio-redis]'")
