"""
CRM Models

Leads, contacts, pipelines, and deals - scoped by project_id for multi-use-case backend.
"""

from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, List, Optional
from uuid import uuid4

from sqlalchemy import String, Text, Integer, ForeignKey, JSON, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.orm.base import Base, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.orm.project import Project
    from app.orm.user import User


class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"


class DealStage(str, Enum):
    LEAD = "lead"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"


class Lead(Base, TimestampMixin, SoftDeleteMixin):
    """Lead model - scoped to project."""

    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(
        String(30),
        default=LeadStatus.NEW.value,
        nullable=False,
    )
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    assigned_to_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    assigned_to: Mapped[Optional["User"]] = relationship("User", lazy="selectin")


class Contact(Base, TimestampMixin, SoftDeleteMixin):
    """Contact model - scoped to project."""

    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")


class Pipeline(Base, TimestampMixin):
    """Pipeline/stage definition for deals."""

    __tablename__ = "pipelines"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    stages: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Ordered list of stage slugs",
    )

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    deals: Mapped[List["Deal"]] = relationship(
        "Deal", back_populates="pipeline", lazy="selectin"
    )


class Deal(Base, TimestampMixin, SoftDeleteMixin):
    """Deal/opportunity - scoped to project."""

    __tablename__ = "deals"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pipeline_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("pipelines.id", ondelete="SET NULL"),
        nullable=True,
    )
    contact_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_to_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    stage: Mapped[str] = mapped_column(
        String(50),
        default=DealStage.LEAD.value,
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    pipeline: Mapped[Optional["Pipeline"]] = relationship(
        "Pipeline", back_populates="deals", lazy="selectin"
    )
