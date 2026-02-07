"""
Stripe Provider

Integration with Stripe for payment processing.
"""

from typing import Optional

from app.core.config import settings


class StripeProvider:
    """Stripe payment provider."""

    def __init__(self):
        self._stripe = None

    @property
    def stripe(self):
        """Lazy load Stripe client."""
        if self._stripe is None:
            try:
                import stripe
                stripe.api_key = settings.STRIPE_SECRET_KEY
                self._stripe = stripe
            except ImportError:
                raise RuntimeError("stripe package not installed")
        return self._stripe

    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Create Stripe customer."""
        customer = self.stripe.Customer.create(
            email=email,
            name=name,
            metadata=metadata or {},
        )
        return customer

    async def get_customer(self, customer_id: str) -> dict:
        """Get Stripe customer."""
        return self.stripe.Customer.retrieve(customer_id)

    async def update_customer(
        self,
        customer_id: str,
        **kwargs,
    ) -> dict:
        """Update Stripe customer."""
        return self.stripe.Customer.modify(customer_id, **kwargs)

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Create Stripe checkout session."""
        session = self.stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                },
            ],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata or {},
        )
        return session

    async def create_billing_portal_session(
        self,
        customer_id: str,
        return_url: str,
    ) -> dict:
        """Create Stripe billing portal session."""
        session = self.stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return session

    async def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True,
    ) -> dict:
        """Cancel Stripe subscription."""
        if at_period_end:
            return self.stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True,
            )
        else:
            return self.stripe.Subscription.delete(subscription_id)

    async def reactivate_subscription(
        self,
        subscription_id: str,
    ) -> dict:
        """Reactivate Stripe subscription."""
        return self.stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=False,
        )

    async def get_subscription(self, subscription_id: str) -> dict:
        """Get Stripe subscription."""
        return self.stripe.Subscription.retrieve(subscription_id)

    def construct_webhook_event(
        self,
        payload: bytes,
        sig_header: str,
    ) -> dict:
        """Construct and verify Stripe webhook event."""
        return self.stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET,
        )
