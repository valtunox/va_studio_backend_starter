"""
E-Commerce Models

Products, orders, and order items - scoped by project_id for multi-use-case backend.
"""

from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, List, Optional
from uuid import uuid4

from sqlalchemy import (
    String,
    Text,
    Boolean,
    Numeric,
    Integer,
    ForeignKey,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.orm.base import Base, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.orm.project import Project
    from app.orm.user import User


class ProductStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Product(Base, TimestampMixin, SoftDeleteMixin):
    """Product model - scoped to project."""

    __tablename__ = "products"

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
    slug: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sku: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)

    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    compare_at_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    cost_per_item: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=ProductStatus.DRAFT.value,
        nullable=False,
    )
    track_inventory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    featured_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    order_items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="product", lazy="selectin"
    )


class Order(Base, TimestampMixin):
    """Order model - scoped to project."""

    __tablename__ = "orders"

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
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=OrderStatus.PENDING.value,
        nullable=False,
    )
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    shipping_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=0, nullable=False
    )

    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    shipping_address: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    billing_address: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    stripe_payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    user: Mapped[Optional["User"]] = relationship("User", lazy="selectin")
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class OrderItem(Base, TimestampMixin):
    """Order line item."""

    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    order_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")
