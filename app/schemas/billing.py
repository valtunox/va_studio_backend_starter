"""
Billing Schemas

Pydantic schemas for billing, subscriptions, and payments.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SubscriptionResponse(BaseModel):
    """Schema for subscription response."""

    id: str
    user_id: str
    plan: str
    status: str
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaymentResponse(BaseModel):
    """Schema for payment response."""

    id: str
    subscription_id: str
    amount: int
    currency: str
    status: str
    description: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @property
    def amount_dollars(self) -> float:
        """Get amount in dollars."""
        return self.amount / 100


class InvoiceResponse(BaseModel):
    """Schema for invoice response."""

    id: str
    subscription_id: str
    invoice_number: str
    amount_due: int
    amount_paid: int
    currency: str
    status: str
    paid_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    invoice_pdf_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateCheckoutSession(BaseModel):
    """Schema for creating Stripe checkout session."""

    plan: str = Field(..., pattern="^(basic|pro|enterprise)$")
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    """Schema for checkout session response."""

    session_id: str
    url: str


class BillingPortalRequest(BaseModel):
    """Schema for billing portal request."""

    return_url: str


class BillingPortalResponse(BaseModel):
    """Schema for billing portal response."""

    url: str


class WebhookEvent(BaseModel):
    """Schema for Stripe webhook event."""

    type: str
    data: dict


class PlanInfo(BaseModel):
    """Schema for plan information."""

    id: str
    name: str
    price: int
    currency: str = "usd"
    interval: str = "month"
    features: list[str] = []
