"""
E-Commerce Routes

Products and orders - scoped by project_id. Use require_project_template
to ensure only ecommerce projects can access these endpoints.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.orm.ecommerce import (
    Product, Order, OrderItem, ProductStatus, OrderStatus,
    Cart, CartItem, WishlistItem,
)
from app.orm.project import Project
from app.orm.user import User
from app.schemas.ecommerce import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    OrderCreate,
    OrderResponse,
    OrderItemResponse,
    CartResponse,
    CartItemCreate,
    CartItemUpdate,
    CartItemResponse,
    WishlistItemCreate,
    WishlistItemResponse,
)
from app.schemas.common import PaginatedResponse
from app.auth.dependencies import get_current_active_user
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
    "/projects/{project_id}/products/public",
    response_model=PaginatedResponse[ProductResponse],
)
async def list_public_products(
    project_id: str,
    q: Optional[str] = Query(None, description="Search query"),
    category_id: Optional[str] = Query(None, description="Filter by category"),
    sort: Optional[str] = Query(
        None, description="Sort field: price_asc, price_desc, newest, rating"
    ),
    page: int = 1,
    per_page: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List active products for a project (public, no auth required)."""
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    skip = (page - 1) * per_page
    query = select(Product).where(
        Product.project_id == project_id,
        Product.is_deleted == False,
        Product.status == ProductStatus.ACTIVE.value,
    )
    if q:
        query = query.where(Product.name.ilike(f"%{q}%"))
    if category_id:
        query = query.where(Product.category_id == category_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    if sort == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc())
    elif sort == "rating":
        query = query.order_by(Product.rating.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    query = query.offset(skip).limit(per_page)
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_create_cart(
    db: AsyncSession, project_id: str, user_id: str
) -> Cart:
    """Return the user's cart for this project, creating one if needed."""
    result = await db.execute(
        select(Cart)
        .options(selectinload(Cart.items).selectinload(CartItem.product))
        .where(Cart.project_id == project_id, Cart.user_id == user_id)
    )
    cart = result.scalar_one_or_none()
    if not cart:
        cart = Cart(project_id=project_id, user_id=user_id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)
        # reload with items relationship
        result = await db.execute(
            select(Cart)
            .options(selectinload(Cart.items).selectinload(CartItem.product))
            .where(Cart.id == cart.id)
        )
        cart = result.scalar_one()
    return cart


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/cart",
    response_model=CartResponse,
)
async def get_cart(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
    current_user: User = Depends(get_current_active_user),
):
    """Get or create the current user's cart."""
    cart = await _get_or_create_cart(db, project_id, current_user.id)
    return cart


@router.post(
    "/projects/{project_id}/cart/items",
    response_model=CartItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_cart_item(
    project_id: str,
    data: CartItemCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
    current_user: User = Depends(get_current_active_user),
):
    """Add an item to the current user's cart."""
    # Validate product exists
    result = await db.execute(
        select(Product).where(
            Product.id == data.product_id,
            Product.project_id == project_id,
            Product.is_deleted == False,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    cart = await _get_or_create_cart(db, project_id, current_user.id)

    # Check if product already in cart — if so, increment quantity
    result = await db.execute(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == data.product_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.quantity += data.quantity
        await db.commit()
        await db.refresh(existing)
        return existing

    item = CartItem(
        cart_id=cart.id,
        product_id=data.product_id,
        quantity=data.quantity,
        unit_price=product.price,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.patch(
    "/projects/{project_id}/cart/items/{item_id}",
    response_model=CartItemResponse,
)
async def update_cart_item(
    project_id: str,
    item_id: str,
    data: CartItemUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
    current_user: User = Depends(get_current_active_user),
):
    """Update quantity of a cart item."""
    cart = await _get_or_create_cart(db, project_id, current_user.id)
    result = await db.execute(
        select(CartItem).where(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    item.quantity = data.quantity
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/projects/{project_id}/cart/items/{item_id}")
async def remove_cart_item(
    project_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
    current_user: User = Depends(get_current_active_user),
):
    """Remove an item from the cart."""
    cart = await _get_or_create_cart(db, project_id, current_user.id)
    result = await db.execute(
        select(CartItem).where(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    await db.delete(item)
    await db.commit()
    return {"message": "Item removed from cart"}


@router.delete("/projects/{project_id}/cart")
async def clear_cart(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
    current_user: User = Depends(get_current_active_user),
):
    """Clear all items from the cart."""
    cart = await _get_or_create_cart(db, project_id, current_user.id)
    for item in cart.items:
        await db.delete(item)
    await db.commit()
    return {"message": "Cart cleared"}


# ---------------------------------------------------------------------------
# Wishlist
# ---------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/wishlist",
    response_model=list[WishlistItemResponse],
)
async def list_wishlist(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
    current_user: User = Depends(get_current_active_user),
):
    """List current user's wishlist items for a project."""
    result = await db.execute(
        select(WishlistItem).where(
            WishlistItem.project_id == project_id,
            WishlistItem.user_id == current_user.id,
        ).order_by(WishlistItem.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/projects/{project_id}/wishlist",
    response_model=WishlistItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_to_wishlist(
    project_id: str,
    data: WishlistItemCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
    current_user: User = Depends(get_current_active_user),
):
    """Add a product to the current user's wishlist."""
    # Validate product exists
    result = await db.execute(
        select(Product).where(
            Product.id == data.product_id,
            Product.project_id == project_id,
            Product.is_deleted == False,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check for duplicate
    result = await db.execute(
        select(WishlistItem).where(
            WishlistItem.project_id == project_id,
            WishlistItem.user_id == current_user.id,
            WishlistItem.product_id == data.product_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product already in wishlist",
        )

    item = WishlistItem(
        project_id=project_id,
        user_id=current_user.id,
        product_id=data.product_id,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/projects/{project_id}/wishlist/{product_id}")
async def remove_from_wishlist(
    project_id: str,
    product_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
    current_user: User = Depends(get_current_active_user),
):
    """Remove a product from the current user's wishlist."""
    result = await db.execute(
        select(WishlistItem).where(
            WishlistItem.project_id == project_id,
            WishlistItem.user_id == current_user.id,
            WishlistItem.product_id == product_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Wishlist item not found")
    await db.delete(item)
    await db.commit()
    return {"message": "Removed from wishlist"}


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------

@router.post(
    "/projects/{project_id}/checkout",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def checkout(
    project_id: str,
    customer_email: Optional[str] = None,
    customer_name: Optional[str] = None,
    shipping_address: Optional[dict] = None,
    billing_address: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireEcommerceProject),
    current_user: User = Depends(get_current_active_user),
):
    """Convert the current user's cart into an order."""
    cart = await _get_or_create_cart(db, project_id, current_user.id)
    if not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cart is empty",
        )

    subtotal = Decimal("0")
    order_items: list[OrderItem] = []
    for ci in cart.items:
        line_total = ci.unit_price * ci.quantity
        subtotal += line_total
        order_items.append(
            OrderItem(
                product_id=ci.product_id,
                quantity=ci.quantity,
                unit_price=ci.unit_price,
                total=line_total,
            )
        )

    # Shipping: free if subtotal >= $50, otherwise $4.99
    shipping = Decimal("0") if subtotal >= Decimal("50") else Decimal("4.99")
    total = subtotal + shipping

    order_number = f"ORD-{int(datetime.now().timestamp())}"

    order = Order(
        project_id=project_id,
        user_id=current_user.id,
        order_number=order_number,
        subtotal=subtotal,
        tax_amount=Decimal("0"),
        shipping_amount=shipping,
        total=total,
        customer_email=customer_email,
        customer_name=customer_name,
        shipping_address=shipping_address,
        billing_address=billing_address,
        items=order_items,
    )
    db.add(order)

    # Clear cart items
    for ci in cart.items:
        await db.delete(ci)

    await db.commit()
    await db.refresh(order)
    return order


# ---------------------------------------------------------------------------
# Public Products (no auth required)
