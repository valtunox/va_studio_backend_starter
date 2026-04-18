"""
Notification Outbox Service (notification domain only)
========================================================

Notification-only logic: write to notification_outbox and process one notification
(email, WebSocket, Redis). Pipeline (poll, retry, DLQ) lives in the queue service.

  - write_to_outbox: call from notification creation (transactional outbox).
  - process_notification_payload: handler used by queue generic outbox processor.
  - mark_notification_dead_letter_callback: used by queue when moving to DLQ.

Usage:
    from app.services.notifications.outbox_service import outbox_service

    # When creating a notification (same transaction)
    await outbox_service.write_to_outbox(notification_id, username, organization, ...)

    # Processing is done by app.services.queue (generic pipeline + this handler).
"""

from app.core.logger import get_logger
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
import asyncpg
from asyncpg import Pool

from app.core.db import async_postgres_connection, release_async_connection

logger = get_logger(__name__)


class OutboxService:
    """Service for managing notification outbox pattern"""
    
    def __init__(self, db_pool: Optional[Pool] = None):
        """
        Initialize outbox service
        
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
    
    def _priority_to_int(self, priority: str) -> int:
        """Convert priority string to integer for outbox"""
        priority_map = {
            'low': 1,
            'normal': 2,
            'high': 3,
            'urgent': 4
        }
        return priority_map.get(priority.lower(), 2)
    
    async def write_to_outbox(
        self,
        notification_id: UUID,
        username: str,
        organization: str,
        event_type: str,
        payload: Dict[str, Any],
        priority: str = "normal",
        scheduled_at: Optional[datetime] = None,
        max_retries: int = 5,
        conn: Optional[asyncpg.Connection] = None
    ) -> UUID:
        """
        Write a notification to the outbox table for reliable queue processing.
        
        This should be called within the same transaction as notification creation
        to ensure atomicity (transactional outbox pattern).
        
        Args:
            notification_id: UUID of the notification
            username: Username of the recipient
            organization: Organization name
            event_type: Type of event (e.g., 'notification.created')
            payload: Full notification data as JSON
            priority: Priority level (low, normal, high, urgent)
            scheduled_at: When to process (default: now)
            max_retries: Maximum retry attempts
            conn: Optional existing database connection (for transactional writes)
            
        Returns:
            UUID of the outbox entry
        """
        use_external_conn = conn is not None
        if not use_external_conn:
            conn = await self._get_connection()
        
        try:
            outbox_id = uuid4()
            now = datetime.utcnow()
            scheduled = scheduled_at or now
            
            query = """
                INSERT INTO notification_outbox 
                (id, notification_id, username, organization, event_type, payload, 
                 priority, status, scheduled_at, created_at, updated_at, max_retries)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id
            """
            
            row = await conn.fetchrow(
                query,
                outbox_id,
                notification_id,
                username,
                organization,
                event_type,
                json.dumps(payload) if isinstance(payload, dict) else payload,
                self._priority_to_int(priority),
                'PENDING',
                scheduled,
                now,
                now,
                max_retries
            )
            
            logger.debug(f"Written notification {notification_id} to outbox {outbox_id}")
            return row['id']
        except Exception as e:
            logger.error(f"Failed to write to outbox: {e}", exc_info=True)
            raise
        finally:
            if not use_external_conn:
                await self._release_connection(conn)

    async def _process_notification(
        self,
        notification_id: UUID,
        payload: Dict[str, Any],
        outbox_entry: Dict[str, Any]
    ) -> bool:
        """
        Internal method to process the actual notification.
        
        This handles sending emails, SMS, push notifications, etc.
        Override or extend this method for custom processing logic.
        """
        try:
            # Update notification status to processing
            conn = await self._get_connection()
            try:
                await conn.execute("""
                    UPDATE notifications
                    SET status = 'processing', updated_at = NOW()
                    WHERE id = $1
                """, notification_id)
            finally:
                await self._release_connection(conn)
            
            # Send email if channel_type is email
            channel_type = payload.get('channel_type', 'in_app')
            if channel_type in ['email', 'all']:
                try:
                    from app.services.notifications.email_service import email_service

                    # Pass payload dict (SQL-only; no models)
                    notification_payload = {
                        "id": str(notification_id),
                        "username": payload.get("username", ""),
                        "organization": payload.get("organization", "xcloud"),
                        "recipient": payload.get("recipient", ""),
                        "title": payload.get("title"),
                        "body": payload.get("body"),
                        "message": payload.get("body"),
                        "channel_type": channel_type,
                        "priority": payload.get("priority", "normal"),
                        "status": "processing",
                        "type": payload.get("type", "info"),
                        "data": payload.get("data"),
                        "metadata": payload.get("metadata"),
                        "created_at": payload.get("created_at", datetime.utcnow()),
                        "sent_at": None,
                        "read_at": None,
                    }
                    email_content = email_service.format_notification_email(notification_payload)
                    email_sent = await email_service.send_notification_email(
                        recipient=payload.get("recipient", ""),
                        subject=email_content["subject"],
                        body=email_content["body"],
                        html_body=email_content.get("html_body"),
                        notification=notification_payload,
                    )
                    
                    if not email_sent:
                        logger.warning(f"Email service returned False for notification {notification_id}")
                except Exception as e:
                    logger.error(f"Failed to send email for notification {notification_id}: {e}", exc_info=True)
                    # Don't fail the whole notification if email fails
            
            # Update notification status to sent
            conn = await self._get_connection()
            try:
                await conn.execute("""
                    UPDATE notifications
                    SET status = 'sent', sent_at = NOW(), updated_at = NOW()
                    WHERE id = $1
                """, notification_id)
            finally:
                await self._release_connection(conn)
            
            # Broadcast via WebSocket and publish to Redis (async, non-blocking)
            try:
                from app.services.notifications.service import notification_service
                from app.services.notifications.websocket import broadcast_notification
                from app.services.notifications.redis_sync import notification_redis_sync
                
                # Reconstruct notification for broadcast
                notification = await notification_service.get_notification(
                    notification_id,
                    payload.get('username', '')
                )
                if notification:
                    await broadcast_notification(notification)
                    await notification_redis_sync.publish_notification(notification)
            except Exception as e:
                logger.warning(f"Failed to broadcast/publish notification: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process notification {notification_id}: {e}", exc_info=True)
            # Update notification status to failed
            try:
                conn = await self._get_connection()
                try:
                    await conn.execute("""
                        UPDATE notifications
                        SET status = 'failed', 
                            error_message = $1,
                            error_code = $2,
                            updated_at = NOW()
                        WHERE id = $3
                    """, str(e), type(e).__name__, notification_id)
                finally:
                    await self._release_connection(conn)
            except Exception as db_error:
                logger.error(f"Failed to update notification status: {db_error}")
            
            raise


# ---------------------------------------------------------------------------
# Handler and callback for queue generic outbox processor
# ---------------------------------------------------------------------------

async def mark_notification_dead_letter_callback(conn, outbox_id, reason: str) -> None:
    """Called by queue when an outbox entry is moved to DEAD_LETTER. Updates notifications table."""
    try:
        row = await conn.fetchrow(
            "SELECT notification_id FROM notification_outbox WHERE id = $1",
            outbox_id,
        )
        if not row:
            return
        notification_id = row["notification_id"]
        await conn.execute("""
            UPDATE notifications
            SET status = 'dead_letter',
                is_dead_letter = TRUE,
                dead_letter_reason = $1,
                dead_letter_at = NOW(),
                updated_at = NOW()
            WHERE id = $2
        """, reason, notification_id)
        logger.info("Notification %s marked as dead letter: %s", notification_id, reason)
    except Exception as e:
        logger.error("Failed to mark notification as dead letter: %s", e, exc_info=True)


async def process_notification_payload(payload: Dict[str, Any], outbox_entry: Dict[str, Any]) -> bool:
    """
    Handler for the queue generic outbox processor. Notification domain only:
    send email, update status, broadcast WebSocket, publish Redis.
    """
    notification_id = outbox_entry.get("notification_id") or payload.get("id")
    if not notification_id:
        logger.error("Outbox entry missing notification_id and payload.id")
        return False
    if isinstance(notification_id, str) and len(notification_id) == 36:
        from uuid import UUID
        notification_id = UUID(notification_id)
    return await outbox_service._process_notification(notification_id, payload, outbox_entry)


# Global outbox service instance (write + _process_notification only)
outbox_service = OutboxService()
