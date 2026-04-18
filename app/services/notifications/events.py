"""
Event Handlers for Notification Triggers
=========================================

This module provides an event bus pattern for triggering notifications from
various system events. It includes handlers for deployment completion, PDF
processing, AI agent events, and custom notifications.

Key Components:
    - NotificationEventBus: Main event bus class with event handlers
    - Convenience functions: Simplified async functions for common events

Event Types:
    - Deployment completion (success, failed, in_progress)
    - PDF processing completion (completed, failed)
    - AI agent events (voice, conversation agents)
    - Custom notifications

All events are processed asynchronously via Celery tasks.

Usage:
    from app.services.notifications.events import notify_deployment_complete
    await notify_deployment_complete(
        username="user123",
        deployment_id="deploy_456",
        deployment_name="My Deployment",
        status="success"
    )
"""

from typing import Dict, Any, Optional
from app.services.notifications.tasks import (
    send_deployment_notification,
    send_pdf_processing_notification,
    create_and_broadcast_notification
)

from app.core.logger import get_logger
logger = get_logger(__name__)


class NotificationEventBus:
    """Event bus for triggering notifications from various events"""
    
    @staticmethod
    async def on_deployment_complete(
        username: str,
        deployment_id: str,
        deployment_name: str,
        status: str = "success",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Trigger notification when deployment completes
        
        Args:
            username: Username who initiated the deployment
            deployment_id: Deployment ID
            deployment_name: Deployment name/identifier
            status: Deployment status (success, failed, in_progress)
            metadata: Optional metadata dictionary
        """
        try:
            logger.info(f"Deployment {deployment_id} completed with status {status} for user {username}")
            
            # Send notification via Celery task
            send_deployment_notification.delay(
                username=username,
                deployment_id=deployment_id,
                deployment_name=deployment_name,
                status=status,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Failed to send deployment notification: {e}", exc_info=True)
    
    @staticmethod
    async def on_pdf_processing_complete(
        username: str,
        file_name: str,
        status: str = "completed",
        processing_result: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Trigger notification when PDF processing completes
        
        Args:
            username: Username who uploaded the PDF
            file_name: Name of the processed file
            status: Processing status (completed, failed)
            processing_result: Optional processing results
            metadata: Optional metadata dictionary
        """
        try:
            logger.info(f"PDF processing {file_name} completed with status {status} for user {username}")
            
            # Send notification via Celery task
            send_pdf_processing_notification.delay(
                username=username,
                file_name=file_name,
                status=status,
                processing_result=processing_result,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Failed to send PDF processing notification: {e}", exc_info=True)
    
    @staticmethod
    async def on_agent_event(
        username: str,
        agent_type: str,
        event_type: str,
        message: str,
        priority: str = "normal",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Trigger notification for AI agent events

        Args:
            username: Username
            agent_type: Type of agent (voice, conversation, etc.)
            event_type: Type of event (completed, failed, started, etc.)
            message: Notification message
            priority: Priority level (low, normal, high, urgent)
            metadata: Optional metadata dictionary
        """
        try:
            logger.info(f"Agent event notification: username={username}, agent_type={agent_type}, event_type={event_type}, priority={priority}")
            title = f"{agent_type.capitalize()} Agent: {event_type.capitalize()}"
            
            # Send notification via Celery task
            create_and_broadcast_notification.delay(
                username=username,
                title=title,
                message=message,
                notification_type='info',
                priority=priority,
                metadata={
                    'agent_type': agent_type,
                    'event_type': event_type,
                    **(metadata or {})
                }
            )
        except Exception as e:
            logger.error(f"Failed to send agent event notification: {e}", exc_info=True)
    
    @staticmethod
    async def send_custom_notification(
        username: str,
        title: str,
        message: str,
        notification_type: str = "info",
        priority: str = "normal",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Send a custom notification

        Args:
            username: Username
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            priority: Priority level
            metadata: Optional metadata dictionary
        """
        try:
            logger.info(f"Sending custom notification: username={username}, title={title}, type={notification_type}, priority={priority}")
            create_and_broadcast_notification.delay(
                username=username,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Failed to send custom notification: {e}", exc_info=True)


# Global event bus instance
notification_event_bus = NotificationEventBus()


# Convenience functions for easy import
async def notify_deployment_complete(
    username: str,
    deployment_id: str,
    deployment_name: str,
    status: str = "success",
    metadata: Optional[Dict[str, Any]] = None
):
    """Convenience function for deployment notifications"""
    logger.info(f"notify_deployment_complete called: username={username}, deployment_id={deployment_id}, status={status}")
    await notification_event_bus.on_deployment_complete(
        username=username,
        deployment_id=deployment_id,
        deployment_name=deployment_name,
        status=status,
        metadata=metadata
    )


async def notify_pdf_processing_complete(
    username: str,
    file_name: str,
    status: str = "completed",
    processing_result: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Convenience function for PDF processing notifications"""
    logger.info(f"notify_pdf_processing_complete called: username={username}, file_name={file_name}, status={status}")
    await notification_event_bus.on_pdf_processing_complete(
        username=username,
        file_name=file_name,
        status=status,
        processing_result=processing_result,
        metadata=metadata
    )
