"""
Notification Models
===================

Pydantic models for the notifications service.
Defines schemas for creating, reading, and updating notifications
and notification preferences.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel


class NotificationCreate(BaseModel):
    """Schema for creating a notification."""

    username: str
    organization: str = "xcloud"
    recipient: Optional[str] = None
    title: str
    message: str
    body: Optional[str] = None
    channel_type: str = "in_app"
    type: Optional[str] = "info"
    priority: str = "normal"
    metadata: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None
    ai_generated_content_1: Optional[Dict[str, Any]] = None
    ai_generated_content_2: Optional[Dict[str, Any]] = None
    reserved_field_1: Optional[str] = None
    event_type: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    max_retries: int = 5


class NotificationRead(BaseModel):
    """Schema for reading a notification."""

    id: UUID
    username: str
    organization: str
    recipient: Optional[str] = None
    title: str
    body: str
    message: str
    channel_type: str
    type: str = "info"
    priority: str = "normal"
    status: str
    data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    ai_generated_content_1: Optional[Dict[str, Any]] = None
    ai_generated_content_2: Optional[Dict[str, Any]] = None
    reserved_field_1: Optional[str] = None

    model_config = {"from_attributes": True}


class NotificationUpdate(BaseModel):
    """Schema for updating a notification."""

    status: Optional[str] = None
    read_at: Optional[datetime] = None
    ai_generated_content_1: Optional[Dict[str, Any]] = None
    ai_generated_content_2: Optional[Dict[str, Any]] = None


class NotificationPreferencesRead(BaseModel):
    """Schema for reading notification preferences."""

    username: str
    organization: Optional[str] = None
    category_id: str
    channel_type: str
    enabled: bool
    updated_at: Optional[datetime] = None
    ai_generated_content_1: Optional[Dict[str, Any]] = None
    ai_generated_content_2: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class NotificationPreferencesUpdate(BaseModel):
    """Schema for updating notification preferences."""

    category_id: Optional[str] = None
    channel_type: Optional[str] = None
    enabled: Optional[bool] = None
