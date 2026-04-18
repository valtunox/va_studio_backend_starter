"""E-Commerce schemas — products, categories, sellers, cart, wishlist, reviews, orders."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Product Category
# ---------------------------------------------------------------------------

class ProductCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = None
    image: Optional[str] = None
    parent_id: Optional[str] = None
    sort_order: int = 0


class ProductCategoryCreate(ProductCategoryBase):
    pass


class ProductCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    slug: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    image: Optional[str] = None
    parent_id: Optional[str] = None
    sort_order: Optional[int] = None


class ProductCategoryResponse(ProductCategoryBase):
    id: str
    project_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Seller
# ---------------------------------------------------------------------------

class SellerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., max_length=255)
    description: Optional[str] = None
    avatar: Optional[str] = None
    location: Optional[str] = None


class SellerCreate(SellerBase):
    pass


class SellerUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    slug: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    location: Optional[str] = None


class SellerResponse(SellerBase):
    id: str
    project_id: str
    user_id: Optional[str] = None
    rating: float = 0.0
    total_products: int = 0
    total_sales: int = 0
    is_verified: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., max_length=255)
    description: Optional[str] = None
    sku: Optional[str] = Field(None, max_length=100)
    price: Decimal = Field(..., ge=0)
    compare_at_price: Optional[Decimal] = Field(None, ge=0)
    discount_percent: Optional[int] = None
    status: str = "draft"
    track_inventory: bool = False
    quantity: int = Field(0, ge=0)
    free_shipping: bool = False
    featured_image: Optional[str] = None
    images: Optional[dict] = None
    category_id: Optional[str] = None
    seller_id: Optional[str] = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    slug: Optional[str] = None
    description: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    compare_at_price: Optional[Decimal] = None
    discount_percent: Optional[int] = None
    status: Optional[str] = None
    track_inventory: Optional[bool] = None
    quantity: Optional[int] = Field(None, ge=0)
    free_shipping: Optional[bool] = None
    featured_image: Optional[str] = None
    images: Optional[dict] = None
    category_id: Optional[str] = None
    seller_id: Optional[str] = None


class ProductResponse(ProductBase):
    id: str
    project_id: str
    rating: float = 0.0
    reviews_count: int = 0
    sold_count: int = 0
    is_flash_deal: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Product Review
# ---------------------------------------------------------------------------

class ProductReviewCreate(BaseModel):
    product_id: str
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = Field(None, max_length=255)
    comment: Optional[str] = None


class ProductReviewResponse(BaseModel):
    id: str
    product_id: str
    user_id: Optional[str] = None
    rating: int
    title: Optional[str] = None
    comment: Optional[str] = None
    is_verified_purchase: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

class CartItemCreate(BaseModel):
    product_id: str
    quantity: int = Field(1, ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1)


class CartItemResponse(BaseModel):
    id: str
    product_id: str
    quantity: int
    unit_price: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class CartResponse(BaseModel):
    id: str
    project_id: str
    user_id: Optional[str] = None
    items: List[CartItemResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Wishlist
# ---------------------------------------------------------------------------

class WishlistItemCreate(BaseModel):
    product_id: str


class WishlistItemResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    product_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

class OrderItemCreate(BaseModel):
    product_id: str
    quantity: int = Field(..., ge=1)
    unit_price: Decimal = Field(..., ge=0)


class OrderItemResponse(BaseModel):
    id: str
    product_id: str
    quantity: int
    unit_price: Decimal
    total: Decimal

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    items: List[OrderItemCreate]
    shipping_address: Optional[dict] = None
    billing_address: Optional[dict] = None


class OrderResponse(BaseModel):
    id: str
    project_id: str
    user_id: Optional[str] = None
    order_number: Optional[str] = None
    status: str
    payment_status: str = "unpaid"
    subtotal: Decimal
    tax_amount: Decimal
    shipping_amount: Decimal
    discount_amount: Decimal = Decimal("0")
    total: Decimal
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    items: List[OrderItemResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}
