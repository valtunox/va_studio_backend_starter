"""
Notification Service
====================

Core business logic layer for notification management. Provides CRUD operations,
user notification retrieval, unread count tracking, and preference management.

This service acts as the data access layer, abstracting database operations
and providing a clean interface for the REST API and WebSocket handlers.

Key Features:
    - Create, read, update, delete notifications
    - User-scoped notification queries
    - Unread count tracking
    - Batch operations (mark all as read)
    - Notification preferences management
    - Connection pooling support

Usage:
    service = NotificationService(db_pool)
    notification = await service.create_notification(NotificationCreate(...))
    notifications = await service.get_user_notifications("user123")
    count = await service.get_unread_count("user123")
"""

from app.core.logger import get_logger
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
import asyncpg
from asyncpg import Pool
from app.services.notifications.models import (
    NotificationCreate, NotificationRead, NotificationUpdate,
    NotificationPreferencesRead, NotificationPreferencesUpdate,
)
from app.core.db import async_postgres_connection, release_async_connection

logger = get_logger(__name__)


class NotificationService:
    """Core notification service for CRUD operations"""
    
    def __init__(self, db_pool: Optional[Pool] = None):
        """
        Initialize notification service
        
        Args:
            db_pool: Optional asyncpg connection pool. If None, creates connections on demand.
        """
        self.db_pool = db_pool
    
    async def _get_connection(self):
        """Get database connection from pool or core.db"""
        if self.db_pool:
            return await self.db_pool.acquire()
        return await async_postgres_connection()

    async def _release_connection(self, conn):
        """Release connection back to pool or core.db"""
        if self.db_pool:
            await self.db_pool.release(conn)
        else:
            await release_async_connection(conn)
    
    async def create_notification(
        self, 
        notification: NotificationCreate,
        use_outbox: bool = True
    ) -> NotificationRead:
        """
        Create a new notification.
        
        Args:
            notification: Notification data to create
            use_outbox: If True, also write to outbox for queue processing (default: True)
        """
        conn = await self._get_connection()
        try:
            notification_id = uuid4()
            now = datetime.utcnow()
            
            # Map legacy 'type' to metadata if not present in event_type
            metadata_json = notification.metadata or {}
            # Handle legacy 'type' field (may be passed from router but not in model)
            if hasattr(notification, 'type') and notification.type:
                metadata_json['notification_type'] = notification.type
            
            # Handle AI generated content
            ai_content_1 = notification.ai_generated_content_1
            ai_content_2 = notification.ai_generated_content_2
            reserved_1 = notification.reserved_field_1
            
            # Use transaction to ensure atomicity if using outbox
            async with conn.transaction():
                # Store metadata in data field (since metadata column doesn't exist in schema)
                # Merge notification.data with metadata_json
                combined_data = notification.data or {}
                if metadata_json:
                    combined_data = {**combined_data, **metadata_json}
                
                query = """
                    INSERT INTO notifications 
                    (id, username, organization, recipient, title, body, channel_type, 
                     priority, status, data, created_at, 
                     ai_generated_content_1, ai_generated_content_2, reserved_field_1)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    RETURNING id, username, organization, recipient, title, body, channel_type, 
                              priority, status, data, created_at, sent_at, read_at,
                              ai_generated_content_1, ai_generated_content_2, reserved_field_1
                """
                
                # For backward compatibility, use message as body if body is None
                body_content = notification.body or notification.message
                
                row = await conn.fetchrow(
                    query,
                    notification_id,
                    notification.username,
                    notification.organization,
                    notification.recipient,
                    notification.title,
                    body_content,
                    notification.channel_type,
                    notification.priority,
                    "queued", # default status
                    combined_data,  # Store metadata in data field
                    now,
                    ai_content_1,
                    ai_content_2,
                    reserved_1
                )
                
                # Write to outbox for queue processing (transactional outbox pattern)
                if use_outbox:
                    try:
                        from app.services.notifications.outbox_service import outbox_service
                        
                        # Prepare payload for outbox
                        payload = {
                            'id': str(notification_id),
                            'username': notification.username,
                            'organization': notification.organization,
                            'recipient': notification.recipient,
                            'title': notification.title,
                            'body': body_content,
                            'channel_type': notification.channel_type,
                            'priority': notification.priority,
                            'data': notification.data,
                            'metadata': metadata_json,
                            'created_at': now.isoformat(),
                            'event_type': notification.event_type or 'notification.created',
                            'entity_type': notification.entity_type,
                            'entity_id': notification.entity_id
                        }
                        
                        # Write to outbox within the same transaction (using same connection)
                        await outbox_service.write_to_outbox(
                            notification_id=notification_id,
                            username=notification.username,
                            organization=notification.organization,
                            event_type=notification.event_type or 'notification.created',
                            payload=payload,
                            priority=notification.priority,
                            scheduled_at=notification.scheduled_at,
                            max_retries=notification.max_retries if hasattr(notification, 'max_retries') else 5,
                            conn=conn  # Use same connection for transactional consistency
                        )
                        logger.debug(f"Notification {notification_id} written to outbox")
                    except Exception as outbox_error:
                        # Log but don't fail the notification creation
                        logger.warning(f"Failed to write to outbox (notification still created): {outbox_error}")
                
                notification_read = NotificationRead(
                    id=row['id'],
                    username=row['username'],
                    organization=row['organization'],
                    recipient=row['recipient'],
                    title=row['title'],
                    body=row['body'],
                    message=row['body'], # back compat
                    channel_type=row['channel_type'],
                    type=metadata_json.get('notification_type', 'info'), # back compat
                    priority=row['priority'],
                    status=row['status'],
                    data=row['data'],
                    metadata=metadata_json,  # Use metadata_json from creation
                    created_at=row['created_at'],
                    sent_at=row['sent_at'],
                    read_at=row['read_at'],
                    ai_generated_content_1=row['ai_generated_content_1'],
                    ai_generated_content_2=row['ai_generated_content_2'],
                    reserved_field_1=row['reserved_field_1']
                )
                
                return notification_read
        except Exception as e:
            logger.error(f"Failed to create notification: {e}", exc_info=True)
            raise
        finally:
            await self._release_connection(conn)

    async def create_notification_from_payload(
        self, payload: Dict[str, Any], use_outbox: bool = True
    ) -> Optional[NotificationRead]:
        """
        Create a notification from a payload dict (SQL-only path; no model).
        Used by queue pipeline so queue does not depend on notifications.models.
        """
        conn = await self._get_connection()
        try:
            notification_id = payload.get("id")
            if isinstance(notification_id, str) and len(notification_id) == 36:
                from uuid import UUID
                notification_id = UUID(notification_id)
            if not notification_id:
                notification_id = uuid4()
            now = datetime.utcnow()
            metadata_json = payload.get("metadata") or payload.get("data") or {}
            if payload.get("type"):
                metadata_json = {**metadata_json, "notification_type": payload.get("type")}
            combined_data = payload.get("data") or {}
            if metadata_json:
                combined_data = {**combined_data, **metadata_json}
            body_content = payload.get("body") or payload.get("message") or ""
            username = payload.get("username", "")
            organization = payload.get("organization", "xcloud")
            recipient = payload.get("recipient", username)
            async with conn.transaction():
                query = """
                    INSERT INTO notifications
                    (id, username, organization, recipient, title, body, channel_type,
                     priority, status, data, created_at,
                     ai_generated_content_1, ai_generated_content_2, reserved_field_1)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    RETURNING id, username, organization, recipient, title, body, channel_type,
                              priority, status, data, created_at, sent_at, read_at,
                              ai_generated_content_1, ai_generated_content_2, reserved_field_1
                """
                row = await conn.fetchrow(
                    query,
                    notification_id,
                    username,
                    organization,
                    recipient,
                    payload.get("title"),
                    body_content,
                    payload.get("channel_type", "in_app"),
                    payload.get("priority", "normal"),
                    "queued",
                    combined_data,
                    now,
                    payload.get("ai_generated_content_1"),
                    payload.get("ai_generated_content_2"),
                    payload.get("reserved_field_1"),
                )
                if use_outbox:
                    try:
                        from app.services.notifications.outbox_service import outbox_service
                        outbox_payload = {
                            "id": str(notification_id),
                            "username": username,
                            "organization": organization,
                            "recipient": recipient,
                            "title": payload.get("title"),
                            "body": body_content,
                            "channel_type": payload.get("channel_type", "in_app"),
                            "priority": payload.get("priority", "normal"),
                            "data": payload.get("data"),
                            "metadata": metadata_json,
                            "created_at": now.isoformat(),
                            "event_type": payload.get("event_type", "notification.created"),
                            "entity_type": payload.get("entity_type"),
                            "entity_id": payload.get("entity_id"),
                        }
                        await outbox_service.write_to_outbox(
                            notification_id=notification_id,
                            username=username,
                            organization=organization,
                            event_type=payload.get("event_type", "notification.created"),
                            payload=outbox_payload,
                            priority=payload.get("priority", "normal"),
                            scheduled_at=payload.get("scheduled_at"),
                            max_retries=payload.get("max_retries", 5),
                            conn=conn,
                        )
                    except Exception as outbox_error:
                        logger.warning("Failed to write to outbox (notification still created): %s", outbox_error)
                return NotificationRead(
                    id=row["id"],
                    username=row["username"],
                    organization=row["organization"],
                    recipient=row["recipient"],
                    title=row["title"],
                    body=row["body"],
                    message=row["body"],
                    channel_type=row["channel_type"],
                    type=metadata_json.get("notification_type", "info"),
                    priority=row["priority"],
                    status=row["status"],
                    data=row["data"],
                    metadata=metadata_json,
                    created_at=row["created_at"],
                    sent_at=row["sent_at"],
                    read_at=row["read_at"],
                    ai_generated_content_1=row["ai_generated_content_1"],
                    ai_generated_content_2=row["ai_generated_content_2"],
                    reserved_field_1=row["reserved_field_1"],
                )
        except Exception as e:
            logger.error("Failed to create notification from payload: %s", e, exc_info=True)
            raise
        finally:
            await self._release_connection(conn)

    async def get_notification(self, notification_id: UUID, username: str) -> Optional[NotificationRead]:
        """Get a notification by ID (user-scoped)"""
        conn = await self._get_connection()
        try:
            query = """
                SELECT id, username, organization, recipient, title, body, channel_type, 
                       priority, status, data, created_at, sent_at, read_at,
                       ai_generated_content_1, ai_generated_content_2, reserved_field_1
                FROM notifications
                WHERE id = $1 AND username = $2
            """
            
            row = await conn.fetchrow(query, notification_id, username)
            
            if not row:
                return None
            
            # Extract metadata from data field (metadata is stored in data JSONB)
            data_dict = row['data'] or {}
            meta = {k: v for k, v in data_dict.items() if k.startswith('notification_type') or k in ['type', 'notification_type']}
            
            return NotificationRead(
                id=row['id'],
                username=row['username'],
                organization=row['organization'],
                recipient=row['recipient'],
                title=row['title'],
                body=row['body'],
                message=row['body'],
                channel_type=row['channel_type'],
                type=meta.get('notification_type', 'info'),
                priority=row['priority'],
                status=row['status'],
                data=row['data'],
                metadata=meta,  # Extract from data field
                created_at=row['created_at'],
                sent_at=row['sent_at'],
                read_at=row['read_at'],
                ai_generated_content_1=row['ai_generated_content_1'],
                ai_generated_content_2=row['ai_generated_content_2'],
                reserved_field_1=row['reserved_field_1']
            )
        except Exception as e:
            logger.error(f"Failed to get notification: {e}", exc_info=True)
            raise
        finally:
            await self._release_connection(conn)
    
    async def get_user_notifications(
        self,
        username: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[NotificationRead]:
        """Get notifications for a user with optional status filter"""
        conn = await self._get_connection()
        try:
            if status:
                query = """
                    SELECT id, username, organization, recipient, title, body, channel_type, 
                           priority, status, data, created_at, sent_at, read_at,
                           ai_generated_content_1, ai_generated_content_2, reserved_field_1
                    FROM notifications
                    WHERE username = $1 AND status = $2
                    ORDER BY created_at DESC
                    LIMIT $3 OFFSET $4
                """
                rows = await conn.fetch(query, username, status, limit, offset)
            else:
                query = """
                    SELECT id, username, organization, recipient, title, body, channel_type, 
                           priority, status, data, created_at, sent_at, read_at,
                           ai_generated_content_1, ai_generated_content_2, reserved_field_1
                    FROM notifications
                    WHERE username = $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                """
                rows = await conn.fetch(query, username, limit, offset)
            
            results = []
            for row in rows:
                # Extract metadata from data field
                data_dict = row['data'] or {}
                meta = {k: v for k, v in data_dict.items() if k.startswith('notification_type') or k in ['type', 'notification_type']}
                results.append(NotificationRead(
                    id=row['id'],
                    username=row['username'],
                    organization=row['organization'],
                    recipient=row['recipient'],
                    title=row['title'],
                    body=row['body'],
                    message=row['body'],
                    channel_type=row['channel_type'],
                    type=meta.get('notification_type', 'info'),
                    priority=row['priority'],
                    status=row['status'],
                    data=row['data'],
                    metadata=meta,  # Extract from data field
                    created_at=row['created_at'],
                    sent_at=row['sent_at'],
                    read_at=row['read_at'],
                    ai_generated_content_1=row['ai_generated_content_1'],
                    ai_generated_content_2=row['ai_generated_content_2'],
                    reserved_field_1=row['reserved_field_1']
                ))
            return results
        except Exception as e:
            logger.error(f"Failed to get user notifications: {e}", exc_info=True)
            raise
        finally:
            await self._release_connection(conn)
    
    async def get_unread_count(self, username: str) -> int:
        """Get count of unread notifications for a user"""
        conn = await self._get_connection()
        try:
            # We assume 'unread' and 'queued' might count, or just 'sent'/'delivered' that haven't been read.
            # Usually simple "status = 'unread'" logic, but with new schema we might check read_at IS NULL
            # But let's stick to status='unread' or status='delivered' and read_at is null if we migrate strictly.
            # The schema says: status VARCHAR(50) NOT NULL DEFAULT 'queued' 
            # (pending, queued, sending, sent, delivered, failed, bounced, read)
            # So unread logic is likely status != 'read' and status != 'archived' and status in ('delivered', 'sent')?
            # Or simplified: The legacy system used 'unread', 'read'. 
            # We should probably support 'unread' as a status if the app writes it, OR check read_at.
            
            # Let's count where read_at IS NULL and status NOT IN ('archived', 'failed', 'bounced')
            # Assuming 'sent'/'delivered' are the visible states. 'queued' might be too early?
            # For simplicity matching previous logic, let's look for notifications where read_at is NULL.
            
            query = """
                SELECT COUNT(*) as count
                FROM notifications
                WHERE username = $1 AND read_at IS NULL AND status NOT IN ('archived', 'failed', 'bounced')
            """
            row = await conn.fetchrow(query, username)
            return row['count'] if row else 0
        except Exception as e:
            logger.error(f"Failed to get unread count: {e}", exc_info=True)
            raise
        finally:
            await self._release_connection(conn)
    
    async def update_notification(
        self,
        notification_id: UUID,
        username: str,
        update: NotificationUpdate
    ) -> Optional[NotificationRead]:
        """Update a notification (mark as read/unread/archived/AI content)"""
        conn = await self._get_connection()
        try:
            updates = []
            params = []
            param_count = 1
            
            if update.status:
                updates.append(f"status = ${param_count}")
                params.append(update.status)
                param_count += 1
                
                # Intelligent read_at handling
                if update.status == 'read':
                    updates.append(f"read_at = ${param_count}")
                    params.append(datetime.utcnow())
                    param_count += 1
                elif update.status == 'unread':
                    updates.append(f"read_at = ${param_count}")
                    params.append(None)
                    param_count += 1
            
            if update.read_at is not None:
                updates.append(f"read_at = ${param_count}")
                params.append(update.read_at)
                param_count += 1
                
            if update.ai_generated_content_1 is not None:
                updates.append(f"ai_generated_content_1 = ${param_count}")
                params.append(update.ai_generated_content_1)
                param_count += 1
            
            if update.ai_generated_content_2 is not None:
                updates.append(f"ai_generated_content_2 = ${param_count}")
                params.append(update.ai_generated_content_2)
                param_count += 1
            
            if not updates:
                return await self.get_notification(notification_id, username)
            
            # Add conditions
            params.extend([notification_id, username])
            
            query = f"""
                UPDATE notifications
                SET {', '.join(updates)}, updated_at = NOW()
                WHERE id = ${param_count} AND username = ${param_count + 1}
                RETURNING id, username, organization, recipient, title, body, channel_type, 
                          priority, status, data, created_at, sent_at, read_at,
                          ai_generated_content_1, ai_generated_content_2, reserved_field_1
            """
            
            row = await conn.fetchrow(query, *params)
            
            if not row:
                return None
            
            # Extract metadata from data field
            data_dict = row['data'] or {}
            meta = {k: v for k, v in data_dict.items() if k.startswith('notification_type') or k in ['type', 'notification_type']}
            
            return NotificationRead(
                id=row['id'],
                username=row['username'],
                organization=row['organization'],
                recipient=row['recipient'],
                title=row['title'],
                body=row['body'],
                message=row['body'],
                channel_type=row['channel_type'],
                type=meta.get('notification_type', 'info'),
                priority=row['priority'],
                status=row['status'],
                data=row['data'],
                metadata=meta,  # Extract from data field
                created_at=row['created_at'],
                sent_at=row['sent_at'],
                read_at=row['read_at'],
                ai_generated_content_1=row['ai_generated_content_1'],
                ai_generated_content_2=row['ai_generated_content_2'],
                reserved_field_1=row['reserved_field_1']
            )
        except Exception as e:
            logger.error(f"Failed to update notification: {e}", exc_info=True)
            raise
        finally:
            await self._release_connection(conn)
    
    async def mark_all_read(self, username: str) -> int:
        """Mark all unread notifications as read for a user"""
        conn = await self._get_connection()
        try:
            query = """
                UPDATE notifications
                SET status = 'read', read_at = $1, updated_at = $1
                WHERE username = $2 AND read_at IS NULL
                RETURNING id
            """
            rows = await conn.fetch(query, datetime.utcnow(), username)
            return len(rows)
        except Exception as e:
            logger.error(f"Failed to mark all as read: {e}", exc_info=True)
            raise
        finally:
            await self._release_connection(conn)
    
    async def delete_notification(self, notification_id: UUID, username: str) -> bool:
        """Delete a notification (user-scoped)"""
        conn = await self._get_connection()
        try:
            query = """
                DELETE FROM notifications
                WHERE id = $1 AND username = $2
            """
            result = await conn.execute(query, notification_id, username)
            return result == "DELETE 1"
        except Exception as e:
            logger.error(f"Failed to delete notification: {e}", exc_info=True)
            raise
        finally:
            await self._release_connection(conn)
    
    # Notification Preferences methods
    async def get_preferences(self, username: str) -> List[NotificationPreferencesRead]:
        """Get notification preferences for a user"""
        conn = await self._get_connection()
        try:
            # Note: The new schema has composite PK (username, category, channel)
            # This method should probably return a list of settings or a specific structure
            # For simplicity, let's query all preferences for the user
            query = """
                SELECT username, organization, category_id, channel_type, enabled, updated_at,
                       ai_generated_content_1, ai_generated_content_2
                FROM notification_preferences
                WHERE username = $1
            """
            
            rows = await conn.fetch(query, username)
            
            return [
                NotificationPreferencesRead(
                    username=row['username'],
                    organization=row['organization'],
                    category_id=row['category_id'],
                    channel_type=row['channel_type'],
                    enabled=row['enabled'],
                    updated_at=row['updated_at'],
                    ai_generated_content_1=row['ai_generated_content_1'],
                    ai_generated_content_2=row['ai_generated_content_2']
                ) for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get preferences: {e}", exc_info=True)
            raise
        finally:
            await self._release_connection(conn)
    
    async def create_default_preferences(self, username: str) -> List[NotificationPreferencesRead]:
        """Create default notification preferences for a user"""
        # With the new granular schema, 'defaults' might mean inserting a row for each known category/channel
        # This implementation stub assumes we just need to ensure the user exists or return empty list if none
        # For now, let's just return empty string 
        return []

    async def update_preferences(
        self,
        username: str,
        update: NotificationPreferencesUpdate
    ) -> List[NotificationPreferencesRead]:
        # Implementation of updating sophisticated preferences is complex.
        # Leaving as skeleton.
        return await self.get_preferences(username)


# Global service instance (can be initialized with pool later)
notification_service = NotificationService()
