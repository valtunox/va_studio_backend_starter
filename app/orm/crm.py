"""
CRM Models

Leads, contacts, pipelines, deals, activities, and tasks —
scoped by project_id for multi-use-case backend.

Matches the frontend CRM template data structures:
  contacts (with status/value), deals (kanban with probability),
  activities feed, tasks, pipeline stages, revenue data.
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, List, Optional
from uuid import uuid4

from sqlalchemy import (
    String,
    Text,
    Boolean,
    Integer,
    Float,
    Numeric,
    ForeignKey,
    JSON,
    DateTime,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.orm.base import Base, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.orm.project import Project
    from app.orm.user import User


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"


class ContactStatus(str, Enum):
    LEAD = "lead"
    PROSPECT = "prospect"
    CUSTOMER = "customer"
    PARTNER = "partner"
    INACTIVE = "inactive"


class DealStage(str, Enum):
    LEAD = "lead"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"


class ActivityType(str, Enum):
    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    NOTE = "note"
    DEAL = "deal"
    TASK = "task"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# ---------------------------------------------------------------------------
# Lead
# ---------------------------------------------------------------------------

class Lead(Base, TimestampMixin, SoftDeleteMixin):
    """Lead — inbound or outbound prospect, scoped to project."""

    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(
        String(30), default=LeadStatus.NEW.value, nullable=False,
    )
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    assigned_to_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    assigned_to: Mapped[Optional["User"]] = relationship("User", lazy="selectin")


# ---------------------------------------------------------------------------
# Contact
# ---------------------------------------------------------------------------

class Contact(Base, TimestampMixin, SoftDeleteMixin):
    """Contact — a person the business interacts with (customer, lead, prospect, partner)."""

    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # Core info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # CRM-specific (frontend: status, value, lastContact)
    status: Mapped[str] = mapped_column(
        String(30), default=ContactStatus.LEAD.value, nullable=False,
    )
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    last_contact_at: Mapped[Optional[str]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    deals: Mapped[List["Deal"]] = relationship(
        "Deal", back_populates="contact", lazy="selectin",
    )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class Pipeline(Base, TimestampMixin):
    """Pipeline definition — named set of stages for deals."""

    __tablename__ = "pipelines"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    stages: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="Ordered list of stage definitions",
    )

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    deals: Mapped[List["Deal"]] = relationship(
        "Deal", back_populates="pipeline", lazy="selectin",
    )


# ---------------------------------------------------------------------------
# Deal
# ---------------------------------------------------------------------------

class Deal(Base, TimestampMixin, SoftDeleteMixin):
    """Deal/opportunity — with probability and days-in-stage for kanban views."""

    __tablename__ = "deals"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    pipeline_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pipelines.id", ondelete="SET NULL"),
        nullable=True,
    )
    contact_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_to_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    stage: Mapped[str] = mapped_column(
        String(50), default=DealStage.LEAD.value, nullable=False,
    )

    # Frontend kanban fields
    probability: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    days_in_stage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expected_close_date: Mapped[Optional[str]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    loss_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    pipeline: Mapped[Optional["Pipeline"]] = relationship(
        "Pipeline", back_populates="deals", lazy="selectin",
    )
    contact: Mapped[Optional["Contact"]] = relationship(
        "Contact", back_populates="deals", lazy="selectin",
    )
    assigned_to: Mapped[Optional["User"]] = relationship("User", lazy="selectin")


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------

class Activity(Base, TimestampMixin):
    """Activity feed entry (call, email, meeting, note, deal update)."""

    __tablename__ = "crm_activities"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    type: Mapped[str] = mapped_column(
        String(30), default=ActivityType.NOTE.value, nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Polymorphic reference to any CRM entity
    related_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    related_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), nullable=True,
    )

    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    user: Mapped[Optional["User"]] = relationship("User", lazy="selectin")


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class CrmTask(Base, TimestampMixin, SoftDeleteMixin):
    """CRM task — to-dos with priority, assignee, and due date."""

    __tablename__ = "crm_tasks"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(
        String(20), default=TaskPriority.MEDIUM.value, nullable=False,
    )
    is_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    due_date: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Assignment
    assigned_to_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assignee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Link to deal/contact
    deal_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("deals.id", ondelete="SET NULL"),
        nullable=True,
    )
    contact_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
    )

    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    assigned_to: Mapped[Optional["User"]] = relationship("User", lazy="selectin")
