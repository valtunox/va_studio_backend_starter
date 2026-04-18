"""
Billing Models

Subscription, payment, and invoice management.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional
from uuid import uuid4

from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.orm.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.orm.user import User


class SubscriptionPlan(str, Enum):
    """Subscription plan types."""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Subscription status."""
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    UNPAID = "unpaid"


class PaymentStatus(str, Enum):
    """Payment status."""
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class Subscription(Base, TimestampMixin):
    """Subscription model."""

    __tablename__ = "subscriptions"

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
        unique=True,
        nullable=False,
        index=True,
    )

    # Stripe
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
    )
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
    )

    # Plan
    plan: Mapped[str] = mapped_column(
        String(50),
        default=SubscriptionPlan.FREE.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=SubscriptionStatus.ACTIVE.value,
        nullable=False,
    )

    # Billing period
    current_period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    current_period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    # Trial
    trial_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    trial_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
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
        back_populates="subscription",
        lazy="selectin",
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        back_populates="subscription",
        lazy="selectin",
    )
    invoices: Mapped[List["Invoice"]] = relationship(
        "Invoice",
        back_populates="subscription",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Subscription {self.id} - {self.plan}>"

    @property
    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self.status in [
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.TRIALING.value,
        ]

    @property
    def is_premium(self) -> bool:
        """Check if subscription is premium."""
        return self.plan in [
            SubscriptionPlan.BASIC.value,
            SubscriptionPlan.PRO.value,
            SubscriptionPlan.ENTERPRISE.value,
        ]


class Payment(Base, TimestampMixin):
    """Payment model."""

    __tablename__ = "payments"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Subscription
    subscription_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Stripe
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
    )
    stripe_invoice_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Amount
    amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="usd",
        nullable=False,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        default=PaymentStatus.PENDING.value,
        nullable=False,
    )

    # Description
    description: Mapped[Optional[str]] = mapped_column(
        Text,
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
    subscription: Mapped["Subscription"] = relationship(
        "Subscription",
        back_populates="payments",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Payment {self.id} - {self.amount} {self.currency}>"

    @property
    def amount_dollars(self) -> float:
        """Get amount in dollars."""
        return self.amount / 100


class Invoice(Base, TimestampMixin):
    """Invoice model."""

    __tablename__ = "invoices"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Subscription
    subscription_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Stripe
    stripe_invoice_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
    )

    # Invoice details
    invoice_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    amount_due: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    amount_paid: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="usd",
        nullable=False,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        default="draft",
        nullable=False,
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # PDF
    invoice_pdf_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Relationships
    subscription: Mapped["Subscription"] = relationship(
        "Subscription",
        back_populates="invoices",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number}>"
