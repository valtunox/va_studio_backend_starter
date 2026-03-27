"""
E-Commerce Models

Products, categories, sellers, cart, wishlist, reviews, orders —
scoped by project_id for multi-use-case backend.

Matches the frontend ecommerce template data structures:
  categories, products (with rating/discount/seller), flash deals,
  cart, wishlist, top sellers, reviews.
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
    Float,
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

class ProductStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


# ---------------------------------------------------------------------------
# Product Category
# ---------------------------------------------------------------------------

class ProductCategory(Base, TimestampMixin):
    """Product category (Electronics, Fashion, Home & Garden, etc.)."""

    __tablename__ = "product_categories"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    parent_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("product_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    parent: Mapped[Optional["ProductCategory"]] = relationship(
        "ProductCategory", remote_side="ProductCategory.id", lazy="selectin",
    )
    products: Mapped[List["Product"]] = relationship(
        "Product", back_populates="category", lazy="selectin",
    )


# ---------------------------------------------------------------------------
# Seller / Store
# ---------------------------------------------------------------------------

class Seller(Base, TimestampMixin, SoftDeleteMixin):
    """Seller/store — marketplace vendor profile."""

    __tablename__ = "sellers"

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

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_products: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_sales: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    user: Mapped[Optional["User"]] = relationship("User", lazy="selectin")
    products: Mapped[List["Product"]] = relationship(
        "Product", back_populates="seller", lazy="selectin",
    )


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

class Product(Base, TimestampMixin, SoftDeleteMixin):
    """Product — with fields matching frontend ecommerce template."""

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    category_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("product_categories.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    seller_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("sellers.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # Core fields
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sku: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)

    # Pricing
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    compare_at_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    cost_per_item: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    discount_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Social proof (frontend: rating, reviews, sold)
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reviews_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sold_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Inventory
    status: Mapped[str] = mapped_column(
        String(20), default=ProductStatus.DRAFT.value, nullable=False,
    )
    track_inventory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Shipping
    free_shipping: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)

    # Media
    featured_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    images: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Flash deal
    is_flash_deal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    flash_deal_end: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)

    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    category: Mapped[Optional["ProductCategory"]] = relationship(
        "ProductCategory", back_populates="products", lazy="selectin",
    )
    seller: Mapped[Optional["Seller"]] = relationship(
        "Seller", back_populates="products", lazy="selectin",
    )
    order_items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="product", lazy="selectin",
    )
    reviews: Mapped[List["ProductReview"]] = relationship(
        "ProductReview", back_populates="product", lazy="selectin",
    )


# ---------------------------------------------------------------------------
# Product Review
# ---------------------------------------------------------------------------

class ProductReview(Base, TimestampMixin, SoftDeleteMixin):
    """Customer review on a product."""

    __tablename__ = "product_reviews"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_verified_purchase: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="reviews")
    user: Mapped[Optional["User"]] = relationship("User", lazy="selectin")


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

class Cart(Base, TimestampMixin):
    """Shopping cart — one per user per project."""

    __tablename__ = "carts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    items: Mapped[List["CartItem"]] = relationship(
        "CartItem", back_populates="cart", lazy="selectin",
        cascade="all, delete-orphan",
    )


class CartItem(Base, TimestampMixin):
    """Individual item in a cart."""

    __tablename__ = "cart_items"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    cart_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")
    product: Mapped["Product"] = relationship("Product", lazy="selectin")


# ---------------------------------------------------------------------------
# Wishlist
# ---------------------------------------------------------------------------

class WishlistItem(Base, TimestampMixin):
    """User wishlist entry."""

    __tablename__ = "wishlist_items"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    product: Mapped["Product"] = relationship("Product", lazy="selectin")


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

class Order(Base, TimestampMixin):
    """Order — scoped to project."""

    __tablename__ = "orders"

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

    order_number: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=OrderStatus.PENDING.value, nullable=False,
    )
    payment_status: Mapped[str] = mapped_column(String(20), default="unpaid", nullable=False)

    # Totals
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    shipping_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Customer info
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    shipping_address: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    billing_address: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Payment
    stripe_payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    user: Mapped[Optional["User"]] = relationship("User", lazy="selectin")
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", lazy="selectin",
        cascade="all, delete-orphan",
    )


class OrderItem(Base, TimestampMixin):
    """Order line item."""

    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    order_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")
