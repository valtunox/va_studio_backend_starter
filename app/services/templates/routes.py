"""
Templates Routes

Endpoints for listing available frontend templates.
These are the starter templates that the chatbot targets
when users select a project type.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional


router = APIRouter(prefix="/templates", tags=["Templates"])


class TemplateInfo(BaseModel):
    """Template metadata."""
    id: str
    name: str
    description: str
    category: str
    icon: str
    features: List[str]
    preview_url: Optional[str] = None


TEMPLATES = [
    TemplateInfo(
        id="saas",
        name="SaaS Dashboard",
        description="Admin dashboard with analytics, user management, and billing integration.",
        category="business",
        icon="bar-chart-3",
        features=["Dashboard", "Analytics", "User Management", "Billing"],
    ),
    TemplateInfo(
        id="portfolio",
        name="Portfolio",
        description="Personal portfolio with projects showcase and contact form.",
        category="personal",
        icon="palette",
        features=["Projects Grid", "About Section", "Contact Form", "Responsive"],
    ),
    TemplateInfo(
        id="ecommerce",
        name="E-Commerce",
        description="Online store with product catalog, cart, and checkout flow.",
        category="business",
        icon="shopping-cart",
        features=["Product Catalog", "Shopping Cart", "Checkout", "Order Tracking"],
    ),
    TemplateInfo(
        id="blog",
        name="Blog / CMS",
        description="Content management with posts, categories, and tags.",
        category="content",
        icon="book-open",
        features=["Posts", "Categories", "Tags", "Rich Editor"],
    ),
    TemplateInfo(
        id="crm",
        name="CRM",
        description="Customer relationship management with contacts and deals pipeline.",
        category="business",
        icon="users",
        features=["Contacts", "Deals Pipeline", "Tasks", "Reports"],
    ),
    TemplateInfo(
        id="erp",
        name="ERP",
        description="Enterprise resource planning with inventory and HR modules.",
        category="enterprise",
        icon="building-2",
        features=["Inventory", "HR", "Finance", "Reporting"],
    ),
]


@router.get("/", response_model=List[TemplateInfo])
async def list_templates() -> List[TemplateInfo]:
    """
    List all available frontend templates.

    Returns the catalog of templates that users can select
    when creating a new project via the chatbot.
    """
    return TEMPLATES


@router.get("/{template_id}", response_model=TemplateInfo)
async def get_template(template_id: str) -> TemplateInfo:
    """Get a specific template by ID."""
    for template in TEMPLATES:
        if template.id == template_id:
            return template
    from fastapi import HTTPException, status
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Template '{template_id}' not found",
    )
