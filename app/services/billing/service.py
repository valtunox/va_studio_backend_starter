"""
Billing Service

Business logic for subscriptions and payments.
"""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.orm.billing import (
    Subscription,
    Payment,
    Invoice,
    SubscriptionPlan,
    SubscriptionStatus,
    PaymentStatus,
)
from app.orm.user import User
from app.core.settings import settings


class BillingService:
    """Billing service for subscription and payment operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # Subscription methods
    async def get_subscription(self, user_id: str) -> Optional[Subscription]:
        """Get user's subscription."""
        result = await self.db.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_subscription(
        self,
        user: User,
        plan: str = SubscriptionPlan.FREE.value,
    ) -> Subscription:
        """Create subscription for user."""
        subscription = Subscription(
            user_id=user.id,
            plan=plan,
            status=SubscriptionStatus.ACTIVE.value,
        )

        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)

        return subscription

    async def update_subscription_plan(
        self,
        subscription: Subscription,
        plan: str,
        stripe_subscription_id: Optional[str] = None,
    ) -> Subscription:
        """Update subscription plan."""
        subscription.plan = plan
        if stripe_subscription_id:
            subscription.stripe_subscription_id = stripe_subscription_id

        await self.db.commit()
        await self.db.refresh(subscription)

        return subscription

    async def cancel_subscription(
        self,
        subscription: Subscription,
        at_period_end: bool = True,
    ) -> Subscription:
        """Cancel subscription."""
        if at_period_end:
            subscription.cancel_at_period_end = True
        else:
            subscription.status = SubscriptionStatus.CANCELED.value

        await self.db.commit()
        await self.db.refresh(subscription)

        return subscription

    async def reactivate_subscription(
        self,
        subscription: Subscription,
    ) -> Subscription:
        """Reactivate canceled subscription."""
        subscription.cancel_at_period_end = False
        subscription.status = SubscriptionStatus.ACTIVE.value

        await self.db.commit()
        await self.db.refresh(subscription)

        return subscription

    # Payment methods
    async def get_payments(
        self,
        subscription_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[Payment], int]:
        """Get payments for subscription."""
        query = select(Payment).where(Payment.subscription_id == subscription_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        query = query.offset(skip).limit(limit).order_by(Payment.created_at.desc())
        result = await self.db.execute(query)
        payments = list(result.scalars().all())

        return payments, total

    async def create_payment(
        self,
        subscription_id: str,
        amount: int,
        currency: str = "usd",
        stripe_payment_intent_id: Optional[str] = None,
    ) -> Payment:
        """Create payment record."""
        payment = Payment(
            subscription_id=subscription_id,
            amount=amount,
            currency=currency,
            stripe_payment_intent_id=stripe_payment_intent_id,
            status=PaymentStatus.PENDING.value,
        )

        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)

        return payment

    async def update_payment_status(
        self,
        payment: Payment,
        status: str,
    ) -> Payment:
        """Update payment status."""
        payment.status = status

        await self.db.commit()
        await self.db.refresh(payment)

        return payment

    # Invoice methods
    async def get_invoices(
        self,
        subscription_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[Invoice], int]:
        """Get invoices for subscription."""
        query = select(Invoice).where(Invoice.subscription_id == subscription_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        query = query.offset(skip).limit(limit).order_by(Invoice.created_at.desc())
        result = await self.db.execute(query)
        invoices = list(result.scalars().all())

        return invoices, total

    async def create_invoice(
        self,
        subscription_id: str,
        amount_due: int,
        invoice_number: str,
        currency: str = "usd",
        due_date: Optional[datetime] = None,
    ) -> Invoice:
        """Create invoice."""
        invoice = Invoice(
            subscription_id=subscription_id,
            invoice_number=invoice_number,
            amount_due=amount_due,
            currency=currency,
            due_date=due_date,
        )

        self.db.add(invoice)
        await self.db.commit()
        await self.db.refresh(invoice)

        return invoice

    # Plan info
    def get_plan_info(self, plan: str) -> dict:
        """Get plan information."""
        plans = {
            SubscriptionPlan.FREE.value: {
                "id": "free",
                "name": "Free",
                "price": 0,
                "currency": "usd",
                "interval": "month",
                "features": [
                    "1 project",
                    "Basic support",
                    "Community access",
                ],
            },
            SubscriptionPlan.BASIC.value: {
                "id": "basic",
                "name": "Basic",
                "price": 999,
                "currency": "usd",
                "interval": "month",
                "stripe_price_id": settings.STRIPE_PRICE_ID_BASIC,
                "features": [
                    "5 projects",
                    "Email support",
                    "API access",
                    "Analytics",
                ],
            },
            SubscriptionPlan.PRO.value: {
                "id": "pro",
                "name": "Pro",
                "price": 2999,
                "currency": "usd",
                "interval": "month",
                "stripe_price_id": settings.STRIPE_PRICE_ID_PRO,
                "features": [
                    "Unlimited projects",
                    "Priority support",
                    "Advanced API",
                    "Advanced analytics",
                    "Custom integrations",
                ],
            },
            SubscriptionPlan.ENTERPRISE.value: {
                "id": "enterprise",
                "name": "Enterprise",
                "price": 9999,
                "currency": "usd",
                "interval": "month",
                "stripe_price_id": settings.STRIPE_PRICE_ID_ENTERPRISE,
                "features": [
                    "Everything in Pro",
                    "Dedicated support",
                    "SLA",
                    "Custom features",
                    "On-premise deployment",
                ],
            },
        }
        return plans.get(plan, plans[SubscriptionPlan.FREE.value])

    def get_all_plans(self) -> list[dict]:
        """Get all available plans."""
        return [
            self.get_plan_info(plan.value)
            for plan in SubscriptionPlan
        ]
