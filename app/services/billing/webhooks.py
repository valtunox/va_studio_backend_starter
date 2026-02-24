"""
Stripe Webhooks

Handle Stripe webhook events.
"""

from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.settings import settings
from app.core.logger import get_logger
from app.orm.billing import Subscription, SubscriptionStatus
from app.services.billing.stripe_provider import StripeProvider


router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
logger = get_logger(__name__)


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Stripe webhook events.

    Processes subscription and payment events from Stripe.
    """
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook secret not configured",
        )

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing signature header",
        )

    stripe_provider = StripeProvider()

    try:
        event = stripe_provider.construct_webhook_event(payload, sig_header)
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )

    event_type = event["type"]
    data = event["data"]["object"]

    logger.info(f"Received Stripe webhook: {event_type}")

    # Handle events
    if event_type == "checkout.session.completed":
        await handle_checkout_completed(db, data)

    elif event_type == "customer.subscription.created":
        await handle_subscription_created(db, data)

    elif event_type == "customer.subscription.updated":
        await handle_subscription_updated(db, data)

    elif event_type == "customer.subscription.deleted":
        await handle_subscription_deleted(db, data)

    elif event_type == "invoice.paid":
        await handle_invoice_paid(db, data)

    elif event_type == "invoice.payment_failed":
        await handle_invoice_payment_failed(db, data)

    return {"status": "success"}


async def handle_checkout_completed(db: AsyncSession, data: dict):
    """Handle checkout session completed event."""
    customer_id = data.get("customer")
    subscription_id = data.get("subscription")
    metadata = data.get("metadata", {})

    if not customer_id or not subscription_id:
        return

    # Get subscription by customer ID
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        plan = metadata.get("plan", "basic")
        subscription.stripe_subscription_id = subscription_id
        subscription.plan = plan
        subscription.status = SubscriptionStatus.ACTIVE.value
        await db.commit()

        logger.info(f"Subscription upgraded to {plan} for customer {customer_id}")


async def handle_subscription_created(db: AsyncSession, data: dict):
    """Handle subscription created event."""
    customer_id = data.get("customer")
    subscription_id = data.get("id")
    status_value = data.get("status")

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        subscription.stripe_subscription_id = subscription_id
        subscription.status = status_value
        await db.commit()


async def handle_subscription_updated(db: AsyncSession, data: dict):
    """Handle subscription updated event."""
    subscription_id = data.get("id")
    status_value = data.get("status")
    cancel_at_period_end = data.get("cancel_at_period_end", False)

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        subscription.status = status_value
        subscription.cancel_at_period_end = cancel_at_period_end
        await db.commit()


async def handle_subscription_deleted(db: AsyncSession, data: dict):
    """Handle subscription deleted event."""
    subscription_id = data.get("id")

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        subscription.status = SubscriptionStatus.CANCELED.value
        subscription.plan = "free"
        subscription.stripe_subscription_id = None
        await db.commit()


async def handle_invoice_paid(db: AsyncSession, data: dict):
    """Handle invoice paid event."""
    subscription_id = data.get("subscription")

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        subscription.status = SubscriptionStatus.ACTIVE.value
        await db.commit()


async def handle_invoice_payment_failed(db: AsyncSession, data: dict):
    """Handle invoice payment failed event."""
    subscription_id = data.get("subscription")

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        subscription.status = SubscriptionStatus.PAST_DUE.value
        await db.commit()
