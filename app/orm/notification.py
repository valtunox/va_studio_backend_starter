"""
Notification Model

In-app and push notifications for users.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import String, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.orm.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.orm.user import User


class NotificationType(str, Enum):
    """Notification type enumeration."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    SYSTEM = "system"
    BILLING = "billing"
    PROJECT = "project"
    COMMENT = "comment"
    MENTION = "mention"


class Notification(Base, TimestampMixin):
    """Notification model."""

    __tablename__ = "notifications"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # User
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Content
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        String(50),
        default=NotificationType.INFO.value,
        nullable=False,
    )

    # Status
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Action
    action_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    action_label: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Reference
    reference_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    reference_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        nullable=True,
    )

    # Metadata
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="notifications",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Notification {self.title}>"

    def mark_as_read(self) -> None:
        """Mark notification as read."""
        self.is_read = True
        self.read_at = datetime.now()
