"""
Template Registry for Dynamic Backend Loading

This module provides a registry system for loading template-specific
services, schemas, and configurations based on the TEMPLATE_TYPE setting.
"""

from enum import Enum
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from fastapi import APIRouter

from app.core.settings import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class TemplateType(str, Enum):
    """Available template types matching frontend templates."""
    SAAS = "saas"
    PORTFOLIO = "portfolio"
    ECOMMERCE = "ecommerce"
    BLOG = "blog"
    CRM = "crm"
    ERP = "erp"
    SOCIAL = "social"
    DASHBOARD = "dashboard"
    LEADS = "leads"


@dataclass
class TemplateConfig:
    """Configuration for a template type."""
    name: str
    description: str
    required_services: List[str] = field(default_factory=list)
    required_middleware: List[str] = field(default_factory=list)
    feature_flags: Dict[str, bool] = field(default_factory=dict)
    requires_redis: bool = False
    requires_celery: bool = False
    requires_billing: bool = False
    requires_kafka: bool = False
    requires_rabbitmq: bool = False


# Template configurations
template_configs: Dict[TemplateType, TemplateConfig] = {
    TemplateType.SAAS: TemplateConfig(
        name="SaaS Template",
        description="Multi-tenant SaaS application with billing, subscriptions, and team management",
        required_services=[
            "auth",
            "users",
            "billing",
            "notifications",
            "analytics",
            "ai",
            "projects",
        ],
        required_middleware=[
            "rate_limit",
            "security_headers",
            "request_logging",
        ],
        feature_flags={
            "enable_billing": True,
            "enable_subscriptions": True,
            "enable_team_management": True,
            "enable_api_keys": True,
            "enable_webhooks": True,
            "enable_oauth": True,
        },
        requires_redis=True,
        requires_celery=True,
        requires_billing=True,
    ),
    
    TemplateType.PORTFOLIO: TemplateConfig(
        name="Portfolio Template",
        description="Personal portfolio website with blog and contact features",
        required_services=[
            "auth",
            "users",
            "blog",
            "health",
        ],
        required_middleware=[
            "security_headers",
            "request_logging",
        ],
        feature_flags={
            "enable_billing": False,
            "enable_subscriptions": False,
            "enable_team_management": False,
            "enable_api_keys": False,
            "enable_webhooks": False,
            "enable_oauth": True,
            "enable_blog": True,
            "enable_contact_form": True,
        },
        requires_redis=False,
        requires_celery=False,
        requires_billing=False,
    ),
    
    TemplateType.ECOMMERCE: TemplateConfig(
        name="E-Commerce Template",
        description="Full e-commerce platform with products, orders, and payments",
        required_services=[
            "auth",
            "users",
            "billing",
            "notifications",
            "analytics",
            "health",
        ],
        required_middleware=[
            "rate_limit",
            "security_headers",
            "request_logging",
        ],
        feature_flags={
            "enable_billing": True,
            "enable_subscriptions": False,
            "enable_inventory": True,
            "enable_orders": True,
            "enable_shipping": True,
            "enable_coupons": True,
            "enable_reviews": True,
            "enable_wishlist": True,
        },
        requires_redis=True,
        requires_celery=True,
        requires_billing=True,
    ),
    
    TemplateType.BLOG: TemplateConfig(
        name="Blog Template",
        description="Content-focused blog platform with comments and subscriptions",
        required_services=[
            "auth",
            "users",
            "blog",
            "notifications",
            "analytics",
            "health",
        ],
        required_middleware=[
            "rate_limit",
            "security_headers",
            "request_logging",
        ],
        feature_flags={
            "enable_billing": False,
            "enable_subscriptions": True,  # Newsletter subscriptions
            "enable_comments": True,
            "enable_categories": True,
            "enable_tags": True,
            "enable_rss": True,
            "enable_newsletter": True,
        },
        requires_redis=True,
        requires_celery=True,
        requires_billing=False,
    ),
    
    TemplateType.CRM: TemplateConfig(
        name="CRM Template",
        description="Customer relationship management with leads, contacts, and pipelines",
        required_services=[
            "auth",
            "users",
            "billing",
            "notifications",
            "analytics",
            "ai",
            "health",
        ],
        required_middleware=[
            "rate_limit",
            "security_headers",
            "request_logging",
        ],
        feature_flags={
            "enable_billing": True,
            "enable_subscriptions": True,
            "enable_leads": True,
            "enable_contacts": True,
            "enable_pipelines": True,
            "enable_tasks": True,
            "enable_activities": True,
            "enable_reports": True,
        },
        requires_redis=True,
        requires_celery=True,
        requires_billing=True,
    ),
    
    TemplateType.ERP: TemplateConfig(
        name="ERP Template",
        description="Enterprise resource planning with inventory and finance modules",
        required_services=[
            "auth",
            "users",
            "billing",
            "notifications",
            "analytics",
            "ai",
            "health",
        ],
        required_middleware=[
            "rate_limit",
            "security_headers",
            "request_logging",
        ],
        feature_flags={
            "enable_billing": True,
            "enable_subscriptions": True,
            "enable_inventory": True,
            "enable_finance": True,
            "enable_procurement": True,
            "enable_manufacturing": True,
        },
        requires_redis=True,
        requires_celery=True,
        requires_billing=True,
        requires_kafka=True,
    ),
    
    TemplateType.SOCIAL: TemplateConfig(
        name="Social Template",
        description="Social media platform with posts, comments, and user interactions",
        required_services=[
            "auth",
            "users",
            "notifications",
            "analytics",
            "health",
        ],
        required_middleware=[
            "rate_limit",
            "security_headers",
            "request_logging",
        ],
        feature_flags={
            "enable_billing": True,
            "enable_subscriptions": True,
            "enable_posts": True,
            "enable_comments": True,
            "enable_likes": True,
            "enable_followers": True,
            "enable_messaging": True,
            "enable_feeds": True,
            "enable_stories": True,
        },
        requires_redis=True,
        requires_celery=True,
        requires_billing=True,
    ),
    
    TemplateType.DASHBOARD: TemplateConfig(
        name="Dashboard Template",
        description="Analytics dashboard with data visualization and reporting",
        required_services=[
            "auth",
            "users",
            "analytics",
            "ai",
            "notifications",
            "health",
        ],
        required_middleware=[
            "rate_limit",
            "security_headers",
            "request_logging",
        ],
        feature_flags={
            "enable_billing": True,
            "enable_subscriptions": True,
            "enable_widgets": True,
            "enable_reports": True,
            "enable_charts": True,
            "enable_data_sources": True,
            "enable_scheduled_reports": True,
            "enable_exports": True,
        },
        requires_redis=True,
        requires_celery=True,
        requires_billing=True,
    ),
    
    TemplateType.LEADS: TemplateConfig(
        name="Leads Management Template",
        description="Lead management with scoring, source tracking, conversion funnel, and pipeline visualization",
        required_services=[
            "auth",
            "users",
            "analytics",
            "ai",
            "notifications",
            "health",
        ],
        required_middleware=[
            "rate_limit",
            "security_headers",
            "request_logging",
        ],
        feature_flags={
            "enable_billing": True,
            "enable_subscriptions": True,
            "enable_leads": True,
            "enable_lead_scoring": True,
            "enable_lead_sources": True,
            "enable_pipeline": True,
            "enable_activities": True,
            "enable_reports": True,
        },
        requires_redis=True,
        requires_celery=True,
        requires_billing=True,
    ),
    
}


class TemplateRegistry:
    """Registry for managing template-specific services and configurations."""
    
    def __init__(self):
        self._routers: Dict[str, APIRouter] = {}
        self._service_loaders: Dict[str, Callable] = {}
        self._middleware_loaders: Dict[str, Callable] = {}
    
    def get_current_template(self) -> TemplateType:
        """Get the current template type from settings."""
        template_str = getattr(settings, 'TEMPLATE_TYPE', 'saas').lower()
        try:
            return TemplateType(template_str)
        except ValueError:
            logger.warning(f"Unknown template type '{template_str}', defaulting to 'saas'")
            return TemplateType.SAAS
    
    def get_template_config(self, template_type: Optional[TemplateType] = None) -> TemplateConfig:
        """Get configuration for a template type."""
        if template_type is None:
            template_type = self.get_current_template()
        return template_configs.get(template_type, template_configs[TemplateType.SAAS])
    
    def register_router(self, name: str, router: APIRouter) -> None:
        """Register a router for a service."""
        self._routers[name] = router
        logger.debug(f"Registered router: {name}")
    
    def register_service_loader(self, name: str, loader: Callable) -> None:
        """Register a service loader function."""
        self._service_loaders[name] = loader
        logger.debug(f"Registered service loader: {name}")
    
    def register_middleware_loader(self, name: str, loader: Callable) -> None:
        """Register a middleware loader function."""
        self._middleware_loaders[name] = loader
        logger.debug(f"Registered middleware loader: {name}")
    
    def get_required_routers(self, template_type: Optional[TemplateType] = None) -> Dict[str, APIRouter]:
        """Get routers required for a template type."""
        config = self.get_template_config(template_type)
        routers = {}
        
        for service_name in config.required_services:
            if service_name in self._routers:
                routers[service_name] = self._routers[service_name]
            else:
                logger.warning(f"Router not found for service: {service_name}")
        
        return routers
    
    def load_service(self, name: str) -> Optional[Any]:
        """Load a service by name."""
        if name in self._service_loaders:
            return self._service_loaders[name]()
        logger.warning(f"No loader found for service: {name}")
        return None
    
    def is_feature_enabled(self, feature_name: str, template_type: Optional[TemplateType] = None) -> bool:
        """Check if a feature is enabled for a template type."""
        config = self.get_template_config(template_type)
        return config.feature_flags.get(feature_name, False)
    
    def requires_service(self, service_name: str, template_type: Optional[TemplateType] = None) -> bool:
        """Check if a service is required for a template type."""
        config = self.get_template_config(template_type)
        return service_name in config.required_services


# Global template registry instance
template_registry = TemplateRegistry()


def get_template_registry() -> TemplateRegistry:
    """Get the global template registry instance."""
    return template_registry
