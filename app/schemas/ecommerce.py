"""E-Commerce schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., max_length=255)
    description: Optional[str] = None
    sku: Optional[str] = Field(None, max_length=100)
    price: Decimal = Field(..., ge=0)
    compare_at_price: Optional[Decimal] = Field(None, ge=0)
    status: str = "draft"
    track_inventory: bool = False
    quantity: int = Field(0, ge=0)
    featured_image: Optional[str] = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    slug: Optional[str] = None
    description: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    compare_at_price: Optional[Decimal] = None
    status: Optional[str] = None
    track_inventory: Optional[bool] = None
    quantity: Optional[int] = Field(None, ge=0)
    featured_image: Optional[str] = None


class ProductResponse(ProductBase):
    id: str
    project_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


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
    items: list[OrderItemCreate]
    shipping_address: Optional[dict] = None
    billing_address: Optional[dict] = None


class OrderResponse(BaseModel):
    id: str
    project_id: str
    user_id: Optional[str] = None
    status: str
    total: Decimal
    subtotal: Decimal
    tax_amount: Decimal
    shipping_amount: Decimal
    customer_email: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
