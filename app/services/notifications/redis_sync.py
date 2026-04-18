"""
Redis Pub/Sub for Notification Synchronization
===============================================

This module provides Redis pub/sub functionality to synchronize notifications
across multiple server instances. When a notification is created on one server,
it's published to Redis and other servers receive it to broadcast to their
connected WebSocket clients.

Features:
    - Cross-server notification synchronization
    - Automatic reconnection with exponential backoff
    - Message history caching
    - Health monitoring

Usage:
    from app.services.notifications.redis_sync import notification_redis_sync
    
    # Publish notification to Redis
    await notification_redis_sync.publish_notification(notification)
    
    # Subscribe to notifications (called automatically on startup)
    await notification_redis_sync.start_listening()
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from redis import asyncio as aioredis
from redis.asyncio import Redis

from app.services.notifications.models import NotificationRead
from app.services.notifications.websocket import broadcast_notification, broadcast_unread_count_update

from app.core.logger import get_logger
logger = get_logger(__name__)


class NotificationRedisSync:
    """
    Redis Pub/Sub client for synchronizing notifications across server instances.
    
    When a notification is created on one server, it publishes to Redis.
    Other servers subscribe and broadcast to their connected WebSocket clients.
    """
    
    def __init__(self, redis_url: str):
        """
        Initialize Redis sync client.

        Args:
            redis_url: Redis connection URL
        """
        logger.info(f"Initializing NotificationRedisSync with redis_url={redis_url}")
        self.redis_url = redis_url
        self.redis: Optional[Redis] = None
        self.pubsub_redis: Optional[Redis] = None
        self.pubsub: Optional[Any] = None
        self.listening_task: Optional[asyncio.Task] = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 1  # seconds
        self.is_listening = False
        
    async def connect(self):
        """Initialize Redis connections"""
        try:
            logger.info(f"Connecting to Redis for notification sync at {self.redis_url}")
            # Main Redis connection for publishing
            self.redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                retry_on_timeout=True,
                max_connections=20
            )
            
            # Separate connection for pub/sub
            self.pubsub_redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                retry_on_timeout=True
            )
            
            # Test connections
            await self.redis.ping()
            await self.pubsub_redis.ping()
            
            logger.info("Redis connections established for notification sync")
            self.reconnect_attempts = 0
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            await self._handle_reconnection()
    
    async def _handle_reconnection(self):
        """Handle Redis reconnection with exponential backoff"""
        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            wait_time = self.reconnect_delay * (2 ** (self.reconnect_attempts - 1))
            logger.info(f"Attempting Redis reconnection {self.reconnect_attempts}/{self.max_reconnect_attempts} in {wait_time}s")
            
            await asyncio.sleep(wait_time)
            await self.connect()
        else:
            logger.error("Max Redis reconnection attempts reached for notification sync")
            self.is_listening = False
    
    async def publish_notification(self, notification: NotificationRead):
        """
        Publish a notification to Redis for cross-server synchronization.

        Args:
            notification: NotificationRead object to publish
        """
        try:
            logger.info(f"Publishing notification to Redis: id={notification.id}, username={notification.username}")
            if not self.redis:
                await self.connect()
            
            # Convert notification to dict
            notification_dict = notification.model_dump()
            # Ensure dates are serializable
            if notification.created_at:
                notification_dict['created_at'] = notification.created_at.isoformat()
            if notification.sent_at:
                notification_dict['sent_at'] = notification.sent_at.isoformat()
            if notification.read_at:
                notification_dict['read_at'] = notification.read_at.isoformat()
            
            # Add metadata
            message = {
                'type': 'new_notification',
                'notification': notification_dict,
                'published_at': datetime.utcnow().isoformat(),
                'server_id': os.getenv('SERVER_ID', 'unknown')
            }
            
            channel = 'notifications:new'
            message_str = json.dumps(message, default=str)
            await self.redis.publish(channel, message_str)
            
            logger.debug(f"Published notification {notification.id} to Redis channel {channel}")
            
        except Exception as e:
            logger.error(f"Failed to publish notification to Redis: {e}")
            await self._handle_reconnection()
    
    async def publish_unread_count_update(self, username: str, count: int):
        """
        Publish unread count update to Redis.

        Args:
            username: Username
            count: New unread count
        """
        try:
            logger.info(f"Publishing unread count update: username={username}, count={count}")
            if not self.redis:
                await self.connect()
            
            message = {
                'type': 'unread_count_update',
                'username': username,
                'count': count,
                'published_at': datetime.utcnow().isoformat(),
                'server_id': os.getenv('SERVER_ID', 'unknown')
            }
            
            channel = 'notifications:unread_count'
            message_str = json.dumps(message, default=str)
            await self.redis.publish(channel, message_str)
            
            logger.debug(f"Published unread count update for {username} to Redis")
            
        except Exception as e:
            logger.error(f"Failed to publish unread count update to Redis: {e}")
    
    async def start_listening(self):
        """Start listening to Redis pub/sub for notifications from other servers"""
        logger.info("Starting to listen for Redis notification channels")
        if self.is_listening:
            logger.warning("Already listening to Redis notifications")
            return
        
        try:
            if not self.pubsub_redis:
                await self.connect()
            
            # Subscribe to notification channels
            self.pubsub = self.pubsub_redis.pubsub()
            await self.pubsub.subscribe(
                'notifications:new',
                'notifications:unread_count'
            )
            
            self.is_listening = True
            logger.info("Started listening to Redis notification channels")
            
            # Start listening task
            self.listening_task = asyncio.create_task(self._listen_loop())
            
        except Exception as e:
            logger.error(f"Failed to start listening to Redis: {e}")
            self.is_listening = False
            await self._handle_reconnection()
    
    async def _listen_loop(self):
        """Main listening loop for Redis messages"""
        logger.info("Entering Redis notification listen loop")
        while self.is_listening:
            try:
                if not self.pubsub:
                    await asyncio.sleep(1)
                    continue
                
                message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                
                if message and message['type'] == 'message':
                    await self._handle_redis_message(message)
                    
            except asyncio.TimeoutError:
                # Normal timeout, continue
                continue
            except Exception as e:
                logger.error(f"Error in Redis listen loop: {e}")
                await asyncio.sleep(1)
    
    async def _handle_redis_message(self, message: Dict[str, Any]):
        """Handle a message received from Redis"""
        try:
            logger.info(f"Handling Redis message from channel={message.get('channel')}")
            channel = message['channel']
            data_str = message['data']
            
            # Skip messages from our own server (avoid duplicate broadcasts)
            server_id = os.getenv('SERVER_ID', 'unknown')
            
            data = json.loads(data_str)
            if data.get('server_id') == server_id:
                # This message came from this server, skip to avoid duplicate
                return
            
            if channel == 'notifications:new':
                await self._handle_new_notification(data)
            elif channel == 'notifications:unread_count':
                await self._handle_unread_count_update(data)
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode Redis message: {e}")
        except Exception as e:
            logger.error(f"Error handling Redis message: {e}", exc_info=True)
    
    async def _handle_new_notification(self, data: Dict[str, Any]):
        """Handle a new notification from Redis"""
        try:
            logger.info(f"Handling new notification from Redis: type={data.get('type')}")
            notification_dict = data.get('notification', {})
            
            # Reconstruct NotificationRead object
            # Note: This is a simplified reconstruction - in production, you might want
            # to fetch from database to ensure consistency
            from datetime import datetime
            from uuid import UUID
            
            notification = NotificationRead(
                id=UUID(notification_dict['id']),
                username=notification_dict['username'],
                organization=notification_dict.get('organization', 'xcloud'),
                recipient=notification_dict.get('recipient', ''),
                title=notification_dict.get('title'),
                body=notification_dict.get('body'),
                channel_type=notification_dict.get('channel_type', 'in_app'),
                priority=notification_dict.get('priority', 'normal'),
                status=notification_dict.get('status', 'queued'),
                data=notification_dict.get('data'),
                created_at=datetime.fromisoformat(notification_dict['created_at'].replace('Z', '+00:00')),
                sent_at=datetime.fromisoformat(notification_dict['sent_at'].replace('Z', '+00:00')) if notification_dict.get('sent_at') else None,
                read_at=datetime.fromisoformat(notification_dict['read_at'].replace('Z', '+00:00')) if notification_dict.get('read_at') else None,
                ai_generated_content_1=notification_dict.get('ai_generated_content_1'),
                ai_generated_content_2=notification_dict.get('ai_generated_content_2'),
                reserved_field_1=notification_dict.get('reserved_field_1')
            )
            
            # Broadcast to WebSocket clients on this server
            await broadcast_notification(notification)
            logger.info(f"Broadcasted notification {notification.id} from Redis to WebSocket clients")
            
        except Exception as e:
            logger.error(f"Failed to handle new notification from Redis: {e}", exc_info=True)
    
    async def _handle_unread_count_update(self, data: Dict[str, Any]):
        """Handle unread count update from Redis"""
        try:
            logger.info(f"Handling unread count update from Redis: username={data.get('username')}, count={data.get('count')}")
            username = data.get('username')
            count = data.get('count', 0)
            
            if username:
                await broadcast_unread_count_update(username, count)
                logger.debug(f"Broadcasted unread count update for {username} from Redis")
                
        except Exception as e:
            logger.error(f"Failed to handle unread count update from Redis: {e}")
    
    async def stop_listening(self):
        """Stop listening to Redis"""
        logger.info("Stopping Redis notification listener")
        self.is_listening = False
        
        if self.listening_task:
            self.listening_task.cancel()
            try:
                await self.listening_task
            except asyncio.CancelledError:
                pass
        
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
            self.pubsub = None
        
        logger.info("Stopped listening to Redis notification channels")
    
    async def close(self):
        """Close Redis connections"""
        logger.info("Closing Redis connections for notification sync")
        await self.stop_listening()
        
        if self.redis:
            await self.redis.close()
            self.redis = None
        
        if self.pubsub_redis:
            await self.pubsub_redis.close()
            self.pubsub_redis = None
        
        logger.info("Closed Redis connections for notification sync")
    
    async def health_check(self) -> bool:
        """Check if Redis connection is healthy"""
        try:
            logger.info("Performing Redis health check for notification sync")
            if self.redis:
                await self.redis.ping()
                return True
            return False
        except Exception:
            return False


# Global instance
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
notification_redis_sync = NotificationRedisSync(REDIS_URL)
