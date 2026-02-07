"""
Notification Schemas

Pydantic schemas for notifications.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class NotificationBase(BaseModel):
    """Base notification schema."""

    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)


class NotificationCreate(NotificationBase):
    """Schema for creating a notification."""

    type: str = "info"
    action_url: Optional[str] = Field(None, max_length=500)
    action_label: Optional[str] = Field(None, max_length=100)
    reference_type: Optional[str] = Field(None, max_length=50)
    reference_id: Optional[str] = None
    metadata: Optional[dict] = None


class NotificationResponse(NotificationBase):
    """Schema for notification response."""

    id: str
    user_id: str
    type: str
    is_read: bool
    read_at: Optional[datetime] = None
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationUpdate(BaseModel):
    """Schema for updating a notification."""

    is_read: Optional[bool] = None


class NotificationBulkAction(BaseModel):
    """Schema for bulk notification actions."""

    notification_ids: list[str]
    action: str = Field(..., pattern="^(mark_read|mark_unread|delete)$")


class UnreadCountResponse(BaseModel):
    """Schema for unread count response."""

    count: int
