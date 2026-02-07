"""
Project Model

Projects/workspaces with ownership and collaboration.
"""

from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import String, Text, Boolean, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.orm.base import Base, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.orm.user import User


class ProjectStatus(str, Enum):
    """Project status enumeration."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DRAFT = "draft"


class Project(Base, TimestampMixin, SoftDeleteMixin):
    """Project model."""

    __tablename__ = "projects"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Basic info
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=ProjectStatus.ACTIVE.value,
        nullable=False,
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Settings
    settings: Mapped[Optional[dict]] = mapped_column(
        JSON,
        default=dict,
        nullable=True,
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=True,
    )

    # Ownership
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="projects",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Project {self.name}>"

    @property
    def is_active(self) -> bool:
        """Check if project is active."""
        return self.status == ProjectStatus.ACTIVE.value
