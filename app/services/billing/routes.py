"""
Billing Routes

Endpoints for subscription and payment management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.settings import settings
from app.orm.user import User
from app.schemas.billing import (
    SubscriptionResponse,
    PaymentResponse,
    InvoiceResponse,
    CreateCheckoutSession,
    CheckoutSessionResponse,
    BillingPortalRequest,
    BillingPortalResponse,
    PlanInfo,
)
from app.schemas.common import PaginatedResponse, MessageResponse
from app.auth.dependencies import get_current_active_user
from app.services.billing.service import BillingService
from app.services.billing.stripe_provider import StripeProvider


router = APIRouter(prefix="/billing", tags=["Billing"])


@router.get("/plans", response_model=list[PlanInfo])
async def list_plans(
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    List available subscription plans.

    Returns all available subscription plans with features.
    """
    service = BillingService(db)
    return service.get_all_plans()


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SubscriptionResponse:
    """
    Get current user's subscription.

    Returns subscription details for the current user.
    """
    service = BillingService(db)
    subscription = await service.get_subscription(current_user.id)

    if not subscription:
        # Create free subscription if none exists
        subscription = await service.create_subscription(current_user)

    return subscription


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    data: CreateCheckoutSession,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Create Stripe checkout session.

    Creates a checkout session for upgrading subscription.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe is not configured",
        )

    service = BillingService(db)
    stripe_provider = StripeProvider()

    # Get or create subscription
    subscription = await service.get_subscription(current_user.id)
    if not subscription:
        subscription = await service.create_subscription(current_user)

    # Get plan info
    plan_info = service.get_plan_info(data.plan)
    price_id = plan_info.get("stripe_price_id")

    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan",
        )

    # Create or get Stripe customer
    if not subscription.stripe_customer_id:
        customer = await stripe_provider.create_customer(
            email=current_user.email,
            name=current_user.full_name,
            metadata={"user_id": current_user.id},
        )
        subscription.stripe_customer_id = customer["id"]
        await db.commit()

    # Create checkout session
    session = await stripe_provider.create_checkout_session(
        customer_id=subscription.stripe_customer_id,
        price_id=price_id,
        success_url=data.success_url,
        cancel_url=data.cancel_url,
        metadata={
            "user_id": current_user.id,
            "plan": data.plan,
        },
    )

    return {"session_id": session["id"], "url": session["url"]}


@router.post("/portal", response_model=BillingPortalResponse)
async def create_billing_portal(
    data: BillingPortalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Create Stripe billing portal session.

    Creates a billing portal for managing subscription.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe is not configured",
        )

    service = BillingService(db)
    stripe_provider = StripeProvider()

    subscription = await service.get_subscription(current_user.id)
    if not subscription or not subscription.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No billing account found",
        )

    session = await stripe_provider.create_billing_portal_session(
        customer_id=subscription.stripe_customer_id,
        return_url=data.return_url,
    )

    return {"url": session["url"]}


@router.post("/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    at_period_end: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SubscriptionResponse:
    """
    Cancel subscription.

    Cancels the current subscription.
    """
    service = BillingService(db)
    subscription = await service.get_subscription(current_user.id)

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No subscription found",
        )

    if subscription.plan == "free":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel free plan",
        )

    return await service.cancel_subscription(subscription, at_period_end)


@router.post("/reactivate", response_model=SubscriptionResponse)
async def reactivate_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SubscriptionResponse:
    """
    Reactivate canceled subscription.

    Reactivates a subscription that was set to cancel at period end.
    """
    service = BillingService(db)
    subscription = await service.get_subscription(current_user.id)

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No subscription found",
        )

    if not subscription.cancel_at_period_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription is not set to cancel",
        )

    return await service.reactivate_subscription(subscription)


@router.get("/payments", response_model=PaginatedResponse[PaymentResponse])
async def list_payments(
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    List payment history.

    Returns paginated list of payments.
    """
    service = BillingService(db)
    subscription = await service.get_subscription(current_user.id)

    if not subscription:
        return PaginatedResponse.create(items=[], total=0, page=page, per_page=per_page)

    skip = (page - 1) * per_page
    payments, total = await service.get_payments(
        subscription_id=subscription.id,
        skip=skip,
        limit=per_page,
    )

    return PaginatedResponse.create(
        items=payments,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/invoices", response_model=PaginatedResponse[InvoiceResponse])
async def list_invoices(
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    List invoices.

    Returns paginated list of invoices.
    """
    service = BillingService(db)
    subscription = await service.get_subscription(current_user.id)

    if not subscription:
        return PaginatedResponse.create(items=[], total=0, page=page, per_page=per_page)

    skip = (page - 1) * per_page
    invoices, total = await service.get_invoices(
        subscription_id=subscription.id,
        skip=skip,
        limit=per_page,
    )

    return PaginatedResponse.create(
        items=invoices,
        total=total,
        page=page,
        per_page=per_page,
    )
