"""
E-Commerce Routes

Products and orders - scoped by project_id. Use require_project_template
to ensure only ecommerce projects can access these endpoints.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.orm.ecommerce import Product, Order, OrderItem, ProductStatus, OrderStatus
from app.orm.project import Project
from app.schemas.ecommerce import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    OrderCreate,
    OrderResponse,
    OrderItemResponse,
)
from app.schemas.common import PaginatedResponse
from app.auth.project_dependencies import get_project_or_404, RequireEcommerceProject

router = APIRouter(prefix="/ecommerce", tags=["E-Commerce"])


# --- Products ---
@router.get(
    "/projects/{project_id}/products",
    response_model=PaginatedResponse[ProductResponse],
)
async def list_products(
    project_id: str,
    page: int = 1,
    per_page: int = 20,
    status: str = None,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
):
    """List products for an ecommerce project."""
    skip = (page - 1) * per_page
    query = select(Product).where(
        Product.project_id == project_id,
        Product.is_deleted == False,
    )
    if status:
        query = query.where(Product.status == status)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(Product.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post(
    "/projects/{project_id}/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    project_id: str,
    data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
):
    """Create a product for an ecommerce project."""
    product = Product(
        project_id=project_id,
        name=data.name,
        slug=data.slug,
        description=data.description,
        sku=data.sku,
        price=data.price,
        compare_at_price=data.compare_at_price,
        status=data.status,
        track_inventory=data.track_inventory,
        quantity=data.quantity,
        featured_image=data.featured_image,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.get(
    "/projects/{project_id}/products/{product_id}",
    response_model=ProductResponse,
)
async def get_product(
    project_id: str,
    product_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
):
    """Get a product by ID."""
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.project_id == project_id,
            Product.is_deleted == False,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch(
    "/projects/{project_id}/products/{product_id}",
    response_model=ProductResponse,
)
async def update_product(
    project_id: str,
    product_id: str,
    data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
):
    """Update a product."""
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.project_id == project_id,
            Product.is_deleted == False,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(product, k, v)
    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/projects/{project_id}/products/{product_id}")
async def delete_product(
    project_id: str,
    product_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
):
    """Soft-delete a product."""
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.project_id == project_id,
            Product.is_deleted == False,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.soft_delete()
    await db.commit()
    return {"message": "Product deleted"}


# --- Orders ---
@router.get(
    "/projects/{project_id}/orders",
    response_model=PaginatedResponse[OrderResponse],
)
async def list_orders(
    project_id: str,
    page: int = 1,
    per_page: int = 20,
    status: str = None,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
):
    """List orders for an ecommerce project."""
    skip = (page - 1) * per_page
    query = select(Order).where(Order.project_id == project_id)
    if status:
        query = query.where(Order.status == status)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(Order.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post(
    "/projects/{project_id}/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    project_id: str,
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
):
    """Create an order for an ecommerce project."""
    subtotal = Decimal("0")
    items_to_create = []
    for item in data.items:
        result = await db.execute(
            select(Product).where(
                Product.id == item.product_id,
                Product.project_id == project_id,
                Product.is_deleted == False,
            )
        )
        prod = result.scalar_one_or_none()
        if not prod:
            raise HTTPException(
                status_code=404,
                detail=f"Product {item.product_id} not found",
            )
        total = item.unit_price * item.quantity
        subtotal += total
        items_to_create.append(
            OrderItem(
                product_id=prod.id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total=total,
            )
        )
    order = Order(
        project_id=project_id,
        subtotal=subtotal,
        total=subtotal,
        tax_amount=Decimal("0"),
        shipping_amount=Decimal("0"),
        customer_email=data.customer_email,
        shipping_address=data.shipping_address,
        billing_address=data.billing_address,
        items=items_to_create,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


@router.get(
    "/projects/{project_id}/orders/{order_id}",
    response_model=OrderResponse,
)
async def get_order(
    project_id: str,
    order_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
):
    """Get an order by ID."""
    result = await db.execute(
        select(Order).where(
            Order.id == order_id,
            Order.project_id == project_id,
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
