"""
SaaS Template Core Services

This module provides core SaaS functionality including:
- Multi-tenancy support
- Subscription management
- Tenant isolation
- Webhook management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

from app.core.logger import logger
from app.templates.service_loader import get_service_loader

router = APIRouter(prefix="/saas", tags=["SaaS"])


class SubscriptionTier(str, Enum):
    """Subscription tiers for SaaS."""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Subscription status."""
    ACTIVE = "active"
    TRIAL = "trial"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"


class TenantBase(BaseModel):
    """Base tenant schema."""
    name: str
    slug: str
    description: Optional[str] = None


class TenantCreate(TenantBase):
    """Create tenant schema."""
    owner_email: str
    plan: SubscriptionTier = SubscriptionTier.FREE


class TenantUpdate(BaseModel):
    """Update tenant schema."""
    name: Optional[str] = None
    description: Optional[str] = None


class TenantResponse(TenantBase):
    """Tenant response schema."""
    id: str
    owner_id: str
    plan: SubscriptionTier
    status: SubscriptionStatus
    created_at: datetime
    updated_at: datetime
    member_count: int
    storage_used: int
    storage_limit: int


class SubscriptionBase(BaseModel):
    """Base subscription schema."""
    tenant_id: str
    tier: SubscriptionTier
    status: SubscriptionStatus


class SubscriptionCreate(BaseModel):
    """Create subscription schema."""
    tier: SubscriptionTier
    payment_method_id: Optional[str] = None
    billing_cycle: str = "monthly"  # monthly, yearly


class SubscriptionResponse(SubscriptionBase):
    """Subscription response schema."""
    id: str
    current_period_start: datetime
    current_period_end: datetime
    trial_end: Optional[datetime] = None
    cancel_at_period_end: bool
    created_at: datetime


class WebhookEndpoint(BaseModel):
    """Webhook endpoint schema."""
    id: str
    url: str
    events: List[str]
    secret: str
    active: bool
    created_at: datetime


class WebhookCreate(BaseModel):
    """Create webhook endpoint schema."""
    url: str
    events: List[str]


class UsageMetrics(BaseModel):
    """Usage metrics for tenant."""
    tenant_id: str
    api_calls: int
    storage_used: int
    bandwidth_used: int
    active_users: int
    period: str


# In-memory storage for demo (replace with database in production)
_tenants: dict = {}
_subscriptions: dict = {}
_webhooks: dict = {}
_usage_metrics: dict = {}


@router.post("/tenants", response_model=TenantResponse)
async def create_tenant(tenant: TenantCreate):
    """Create a new tenant/organization."""
    tenant_id = f"tenant_{len(_tenants) + 1}"
    now = datetime.utcnow()
    
    new_tenant = {
        "id": tenant_id,
        "name": tenant.name,
        "slug": tenant.slug,
        "description": tenant.description,
        "owner_id": f"user_{tenant.owner_email}",
        "plan": tenant.plan,
        "status": SubscriptionStatus.TRIAL,
        "created_at": now,
        "updated_at": now,
        "member_count": 1,
        "storage_used": 0,
        "storage_limit": 1073741824 if tenant.plan == SubscriptionTier.FREE else 10737418240,  # 1GB or 10GB
    }
    
    _tenants[tenant_id] = new_tenant
    
    # Create initial subscription
    subscription_id = f"sub_{len(_subscriptions) + 1}"
    trial_end = datetime.utcnow()
    trial_end = trial_end.replace(day=trial_end.day + 14)  # 14-day trial
    
    _subscriptions[subscription_id] = {
        "id": subscription_id,
        "tenant_id": tenant_id,
        "tier": tenant.plan,
        "status": SubscriptionStatus.TRIAL,
        "current_period_start": now,
        "current_period_end": trial_end,
        "trial_end": trial_end,
        "cancel_at_period_end": False,
        "created_at": now,
    }
    
    logger.info(f"Created tenant: {tenant.name} ({tenant_id}) with {tenant.plan} plan")
    return TenantResponse(**new_tenant)


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: str):
    """Get tenant details."""
    if tenant_id not in _tenants:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return TenantResponse(**_tenants[tenant_id])


@router.put("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(tenant_id: str, tenant_update: TenantUpdate):
    """Update tenant details."""
    if tenant_id not in _tenants:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    existing = _tenants[tenant_id]
    update_data = tenant_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        existing[field] = value
    
    existing["updated_at"] = datetime.utcnow()
    
    logger.info(f"Updated tenant: {tenant_id}")
    return TenantResponse(**existing)


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(tenant_id: str):
    """Delete a tenant."""
    if tenant_id not in _tenants:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    del _tenants[tenant_id]
    
    # Clean up related subscriptions
    subs_to_delete = [k for k, v in _subscriptions.items() if v["tenant_id"] == tenant_id]
    for sub_id in subs_to_delete:
        del _subscriptions[sub_id]
    
    logger.info(f"Deleted tenant: {tenant_id}")
    return {"message": "Tenant deleted successfully"}


@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(skip: int = 0, limit: int = 100):
    """List all tenants."""
    tenants = list(_tenants.values())[skip:skip + limit]
    return [TenantResponse(**t) for t in tenants]


@router.post("/subscriptions", response_model=SubscriptionResponse)
async def create_subscription(subscription: SubscriptionCreate, tenant_id: str):
    """Create a new subscription for a tenant."""
    if tenant_id not in _tenants:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    subscription_id = f"sub_{len(_subscriptions) + 1}"
    now = datetime.utcnow()
    
    # Calculate period end based on billing cycle
    if subscription.billing_cycle == "yearly":
        period_end = now.replace(year=now.year + 1)
    else:
        period_end = now.replace(month=now.month + 1)
    
    new_subscription = {
        "id": subscription_id,
        "tenant_id": tenant_id,
        "tier": subscription.tier,
        "status": SubscriptionStatus.ACTIVE,
        "current_period_start": now,
        "current_period_end": period_end,
        "trial_end": None,
        "cancel_at_period_end": False,
        "created_at": now,
    }
    
    _subscriptions[subscription_id] = new_subscription
    
    # Update tenant plan
    _tenants[tenant_id]["plan"] = subscription.tier
    _tenants[tenant_id]["status"] = SubscriptionStatus.ACTIVE
    
    logger.info(f"Created subscription: {subscription_id} for tenant {tenant_id}")
    return SubscriptionResponse(**new_subscription)


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(subscription_id: str):
    """Get subscription details."""
    if subscription_id not in _subscriptions:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return SubscriptionResponse(**_subscriptions[subscription_id])


@router.put("/subscriptions/{subscription_id}/cancel")
async def cancel_subscription(subscription_id: str, at_period_end: bool = True):
    """Cancel a subscription."""
    if subscription_id not in _subscriptions:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    _subscriptions[subscription_id]["cancel_at_period_end"] = at_period_end
    
    if not at_period_end:
        _subscriptions[subscription_id]["status"] = SubscriptionStatus.CANCELLED
        tenant_id = _subscriptions[subscription_id]["tenant_id"]
        _tenants[tenant_id]["status"] = SubscriptionStatus.CANCELLED
    
    logger.info(f"Cancelled subscription: {subscription_id}")
    return {"message": "Subscription cancelled", "at_period_end": at_period_end}


@router.post("/webhooks", response_model=WebhookEndpoint)
async def create_webhook(webhook: WebhookCreate, tenant_id: str):
    """Create a webhook endpoint for tenant.""""
    if tenant_id not in _tenants:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    webhook_id = f"wh_{len(_webhooks) + 1}"
    import secrets
    
    new_webhook = {
        "id": webhook_id,
        "tenant_id": tenant_id,
        "url": webhook.url,
        "events": webhook.events,
        "secret": secrets.token_urlsafe(32),
        "active": True,
        "created_at": datetime.utcnow(),
    }
    
    _webhooks[webhook_id] = new_webhook
    logger.info(f"Created webhook: {webhook_id} for tenant {tenant_id}")
    
    # Don't return the secret in production, only on creation
    return WebhookEndpoint(**new_webhook)


@router.get("/webhooks", response_model=List[WebhookEndpoint])
async def list_webhooks(tenant_id: str):
    """List webhooks for a tenant."""
    webhooks = [w for w in _webhooks.values() if w.get("tenant_id") == tenant_id]
    # Remove secrets from response
    for w in webhooks:
        w["secret"] = "***"
    return [WebhookEndpoint(**w) for w in webhooks]


@router.get("/usage/{tenant_id}", response_model=UsageMetrics)
async def get_usage_metrics(tenant_id: str):
    """Get usage metrics for a tenant."""
    if tenant_id not in _tenants:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Return mock metrics or stored metrics
    if tenant_id in _usage_metrics:
        return UsageMetrics(**_usage_metrics[tenant_id])
    
    # Generate default metrics
    metrics = {
        "tenant_id": tenant_id,
        "api_calls": 0,
        "storage_used": _tenants[tenant_id]["storage_used"],
        "bandwidth_used": 0,
        "active_users": _tenants[tenant_id]["member_count"],
        "period": "current_month",
    }
    
    return UsageMetrics(**metrics)


@router.get("/config")
async def get_saas_config():
    """Get SaaS configuration and available plans."""
    return {
        "plans": [
            {
                "tier": SubscriptionTier.FREE,
                "name": "Free",
                "price": 0,
                "features": ["1 project", "1GB storage", "Community support"],
                "limits": {"projects": 1, "storage": 1073741824, "team_members": 1},
            },
            {
                "tier": SubscriptionTier.BASIC,
                "name": "Basic",
                "price": 9,
                "price_currency": "USD",
                "features": ["5 projects", "10GB storage", "Email support"],
                "limits": {"projects": 5, "storage": 10737418240, "team_members": 5},
            },
            {
                "tier": SubscriptionTier.PRO,
                "name": "Pro",
                "price": 29,
                "price_currency": "USD",
                "features": ["Unlimited projects", "100GB storage", "Priority support", "API access"],
                "limits": {"projects": -1, "storage": 107374182400, "team_members": 20},
            },
            {
                "tier": SubscriptionTier.ENTERPRISE,
                "name": "Enterprise",
                "price": "custom",
                "features": ["Unlimited everything", "Custom integrations", "Dedicated support", "SLA"],
                "limits": {"projects": -1, "storage": -1, "team_members": -1},
            },
        ]
    }
