"""
Templates Routes (Public)

Public endpoints for browsing and previewing available frontend templates.
No authentication required - this is the entry point for new users.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional, Dict


router = APIRouter(prefix="/templates", tags=["Templates"])


class TemplateFeature(BaseModel):
    """A single feature of a template."""
    name: str
    description: str
    icon: str


class TemplateInfo(BaseModel):
    """Full template metadata for public browsing."""
    id: str
    name: str
    description: str
    category: str
    icon: str
    color_scheme: str
    features: List[str]
    tech_stack: List[str]
    preview_url: Optional[str] = None
    thumbnail: Optional[str] = None
    sections: List[str]
    use_cases: List[str]
    is_premium: bool = False


class TemplatePreview(BaseModel):
    """Template preview configuration returned to the frontend."""
    id: str
    name: str
    color_scheme: str
    default_config: Dict
    sample_data: Dict


TEMPLATES: List[TemplateInfo] = [
    TemplateInfo(
        id="ecommerce",
        name="E-Commerce Store",
        description="Full-featured online store with product catalog, shopping cart, flash deals, and checkout flow.",
        category="business",
        icon="shopping-cart",
        color_scheme="emerald",
        features=["Product Catalog", "Shopping Cart", "Flash Deals", "Wishlist", "Category Filters", "Newsletter"],
        tech_stack=["React", "Tailwind CSS", "Lucide Icons", "Headless UI"],
        thumbnail="https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=400&h=300&fit=crop",
        sections=["Promo Bar", "Hero", "Trust Badges", "Categories", "Featured Products", "Banner CTA", "Flash Deals", "Testimonials", "Brands", "Newsletter", "Footer"],
        use_cases=["Online retail", "Digital products", "Marketplace", "Dropshipping"],
    ),
    TemplateInfo(
        id="saas",
        name="SaaS Landing Page",
        description="Modern SaaS landing page with pricing tiers, feature grid, FAQ, testimonials, and conversion-optimized CTAs.",
        category="business",
        icon="rocket",
        color_scheme="blue",
        features=["Pricing Tables", "Feature Grid", "FAQ Accordion", "Testimonials", "Annual Toggle", "CTA Sections"],
        tech_stack=["React", "Tailwind CSS", "Lucide Icons", "Headless UI"],
        thumbnail="https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=400&h=300&fit=crop",
        sections=["Hero", "Logos", "Features", "Product Screenshot", "Pricing", "Testimonials", "FAQ", "CTA", "Footer"],
        use_cases=["SaaS products", "Developer tools", "API platforms", "B2B software"],
    ),
    TemplateInfo(
        id="portfolio",
        name="Developer Portfolio",
        description="Creative developer portfolio with project gallery, skill bars, experience timeline, and contact form.",
        category="personal",
        icon="palette",
        color_scheme="violet",
        features=["Project Gallery", "Skill Bars", "Experience Timeline", "Testimonials", "Contact Form", "Dark Theme"],
        tech_stack=["React", "Tailwind CSS", "Lucide Icons"],
        thumbnail="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=300&fit=crop",
        sections=["Hero", "Services", "Skills", "Projects", "Experience", "Testimonials", "Contact", "Footer"],
        use_cases=["Developer portfolio", "Freelancer website", "Personal brand", "Resume site"],
    ),
    TemplateInfo(
        id="blog",
        name="Developer Blog",
        description="Magazine-style blog with featured posts, category filters, trending sidebar, author profiles, and newsletter.",
        category="content",
        icon="pen-tool",
        color_scheme="amber",
        features=["Featured Post Hero", "Category Tabs", "Trending Sidebar", "Author Profiles", "Tag Cloud", "Newsletter"],
        tech_stack=["React", "Tailwind CSS", "Lucide Icons"],
        thumbnail="https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=400&h=300&fit=crop",
        sections=["Featured Post", "Article Feed", "Trending", "Authors", "Tags", "Newsletter", "Footer"],
        use_cases=["Tech blog", "Company blog", "Tutorial site", "News platform"],
    ),
    TemplateInfo(
        id="crm",
        name="CRM Dashboard",
        description="Customer relationship management with sales pipeline, contacts table, activity feed, and task management.",
        category="business",
        icon="target",
        color_scheme="violet",
        features=["Sales Pipeline", "Contacts Table", "Activity Feed", "Task Manager", "Deal Tracking", "Stats Cards"],
        tech_stack=["React", "Tailwind CSS", "Lucide Icons"],
        thumbnail="https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=400&h=300&fit=crop",
        sections=["Stats", "Pipeline", "Contacts Table", "Activity Feed", "Tasks"],
        use_cases=["Sales teams", "Customer management", "Lead tracking", "Business development"],
    ),
    TemplateInfo(
        id="erp",
        name="ERP Suite",
        description="Enterprise resource planning dashboard with inventory management, order tracking, warehouse monitoring, and financial KPIs.",
        category="enterprise",
        icon="layers",
        color_scheme="sky",
        features=["KPI Dashboard", "Order Management", "Inventory Alerts", "Warehouse Monitoring", "Purchase Orders", "Financial Reports"],
        tech_stack=["React", "Tailwind CSS", "Lucide Icons"],
        thumbnail="https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=400&h=300&fit=crop",
        sections=["KPIs", "Orders Table", "Warehouses", "Purchase Orders", "Low Stock Alerts"],
        use_cases=["Manufacturing", "Supply chain", "Warehouse management", "Enterprise operations"],
    ),
    TemplateInfo(
        id="social",
        name="Social Platform",
        description="Social media platform with stories, post feed, trending topics, messaging preview, and user suggestions.",
        category="social",
        icon="sparkles",
        color_scheme="rose",
        features=["Stories", "Post Feed", "Trending Topics", "User Suggestions", "Messages", "Like/Repost/Bookmark"],
        tech_stack=["React", "Tailwind CSS", "Lucide Icons"],
        thumbnail="https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=400&h=300&fit=crop",
        sections=["Stories", "Compose", "Feed", "Trending", "Suggested Users", "Messages"],
        use_cases=["Social network", "Community platform", "Forum", "Content sharing"],
    ),
    TemplateInfo(
        id="dashboard",
        name="Analytics Dashboard",
        description="Data analytics dashboard with sparkline charts, revenue breakdowns, device stats, top pages, and transaction tables.",
        category="analytics",
        icon="bar-chart-3",
        color_scheme="indigo",
        features=["Sparkline Charts", "Revenue by Channel", "Device Breakdown", "Top Pages", "Transactions", "Alerts"],
        tech_stack=["React", "Tailwind CSS", "Lucide Icons", "SVG Charts"],
        thumbnail="https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=400&h=300&fit=crop",
        sections=["KPIs", "Revenue Channels", "Devices", "Top Pages", "Transactions", "Alerts"],
        use_cases=["Business analytics", "Marketing dashboard", "Admin panel", "Reporting tool"],
    ),
    TemplateInfo(
        id="login",
        name="Login Page",
        description="Beautiful split-screen login with social auth buttons, dark/light theme toggle, email form, and responsive mobile layout.",
        category="auth",
        icon="log-in",
        color_scheme="indigo",
        features=["Social Login", "Dark/Light Toggle", "Email Form", "Remember Me", "Forgot Password", "Responsive"],
        tech_stack=["React", "Tailwind CSS", "Lucide Icons", "shadcn/ui"],
        thumbnail="https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=400&h=300&fit=crop",
        sections=["Branding Panel", "Login Form", "Social Auth", "Footer Links"],
        use_cases=["SaaS login", "App authentication", "Member portal", "Admin login"],
    ),
    TemplateInfo(
        id="register",
        name="Registration Page",
        description="Registration form with password strength indicator, real-time validation, social signup, terms acceptance, and split-screen branding.",
        category="auth",
        icon="user-plus",
        color_scheme="violet",
        features=["Password Strength", "Real-time Validation", "Social Signup", "Terms Checkbox", "Split Screen", "Responsive"],
        tech_stack=["React", "Tailwind CSS", "Lucide Icons", "shadcn/ui"],
        thumbnail="https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=400&h=300&fit=crop",
        sections=["Branding Panel", "Register Form", "Password Checks", "Social Auth"],
        use_cases=["User registration", "Account creation", "Signup flow", "Onboarding entry"],
    ),
    TemplateInfo(
        id="onboarding",
        name="Onboarding Wizard",
        description="Multi-step onboarding flow with progress bar, profile setup, company info, preferences selection, and completion celebration.",
        category="auth",
        icon="compass",
        color_scheme="indigo",
        features=["Multi-Step Wizard", "Progress Bar", "Profile Setup", "Preferences", "Integrations", "Completion State"],
        tech_stack=["React", "Tailwind CSS", "Lucide Icons", "shadcn/ui"],
        thumbnail="https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=400&h=300&fit=crop",
        sections=["Progress Steps", "Profile Form", "Company Form", "Preferences", "Success"],
        use_cases=["User onboarding", "Account setup", "First-run experience", "Product tour"],
    ),
    TemplateInfo(
        id="leads",
        name="Leads Manager",
        description="Lead management dashboard with scoring, source tracking, conversion funnel, pipeline visualization, and real-time activity feed.",
        category="business",
        icon="target",
        color_scheme="blue",
        features=["Lead Scoring", "Source Tracking", "Conversion Funnel", "Pipeline View", "Activity Feed", "Filter Tabs"],
        tech_stack=["React", "Tailwind CSS", "Lucide Icons", "shadcn/ui"],
        thumbnail="https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=400&h=300&fit=crop",
        sections=["KPIs", "Filter Tabs", "Leads Table", "Lead Sources", "Activity Feed", "Conversion Funnel"],
        use_cases=["Sales teams", "Lead generation", "Marketing qualified leads", "Business development"],
    ),
]

# Index for quick lookup
_templates_by_id = {t.id: t for t in TEMPLATES}


@router.get("/", response_model=List[TemplateInfo])
async def list_templates() -> List[TemplateInfo]:
    """
    List all available frontend templates.

    Public endpoint - no authentication required.
    Returns the full catalog of templates for browsing.
    """
    return TEMPLATES


@router.get("/categories")
async def list_categories() -> List[dict]:
    """
    List template categories with counts.

    Public endpoint - no authentication required.
    """
    categories = {}
    for t in TEMPLATES:
        if t.category not in categories:
            categories[t.category] = {"name": t.category, "count": 0, "templates": []}
        categories[t.category]["count"] += 1
        categories[t.category]["templates"].append(t.id)
    return list(categories.values())


@router.get("/{template_id}", response_model=TemplateInfo)
async def get_template(template_id: str) -> TemplateInfo:
    """
    Get a specific template by ID.

    Public endpoint - no authentication required.
    """
    template = _templates_by_id.get(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_id}' not found",
        )
    return template


@router.get("/{template_id}/preview", response_model=TemplatePreview)
async def get_template_preview(template_id: str) -> TemplatePreview:
    """
    Get template preview configuration.

    Public endpoint - returns config data the frontend uses
    to render a live preview of the template.
    """
    template = _templates_by_id.get(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_id}' not found",
        )
    return TemplatePreview(
        id=template.id,
        name=template.name,
        color_scheme=template.color_scheme,
        default_config={
            "brand_name": "My Company",
            "primary_color": template.color_scheme,
            "sections": template.sections,
            "features": template.features,
        },
        sample_data={
            "template_type": template.id,
            "category": template.category,
            "use_cases": template.use_cases,
        },
    )
