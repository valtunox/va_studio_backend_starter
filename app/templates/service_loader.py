"""
Dynamic Service Loader

This module handles dynamic loading of services based on the configured template type.
Services are loaded on-demand based on the template configuration.
"""

import importlib
from typing import Optional, Dict, Any, List
from fastapi import APIRouter

from app.core.settings import settings
from app.core.logger import get_logger
from app.templates.registry import (
    TemplateType,
    TemplateConfig,
    template_registry,
    template_configs,
)

logger = get_logger(__name__)


class ServiceLoader:
    """
    Dynamic service loader - loads ALL routers for multi-use-case backend
    (valtunox/valtunox studio style). Project template_type determines feature access per route.
    """

    # Public services — always loaded, no auth required
    PUBLIC_SERVICES = ["health", "templates", "chat"]

    # All services to load (single backend for all use cases)
    ALL_SERVICES = [
        "health",
        "templates",
        "chat",
        "auth",
        "oauth",
        "users",
        "projects",
        "billing",
        "webhooks",
        "notifications",
        "analytics",
        "blog",
        "ai",
        "saas",
        "portfolio",
        "ecommerce",
        "crm",
        "erp",
        "leads",
        "candidates",
    ]

    # Service module mappings
    SERVICE_MODULES = {
        # Public services (no auth)
        "health": ("app.services.health.routes", "router"),
        "templates": ("app.services.templates.routes", "router"),
        "chat": ("app.services.chat.routes", "router"),
        # Auth services (loaded when template requires them)
        "auth": ("app.auth.routes", "router"),
        "oauth": ("app.auth.oauth", "router"),
        "users": ("app.services.users.routes", "router"),
        "projects": ("app.services.projects.routes", "router"),
        "billing": ("app.services.billing.routes", "router"),
        "webhooks": ("app.services.billing.webhooks", "router"),
        "notifications": ("app.services.notifications.notifications_services_router", "router"),
        "analytics": ("app.services.analytics.routes", "router"),
        "blog": ("app.services.blog.routes", "router"),
        "ai": ("app.services.ai.routes", "router"),
        # Template-specific services
        "saas": ("app.services.saas.core.routes", "router"),
        "portfolio": ("app.services.portfolio.routes", "router"),
        "ecommerce": ("app.services.ecommerce.routes", "router"),
        "crm": ("app.services.crm.routes", "router"),
        "erp": ("app.services.erp.routes", "router"),
        "leads": ("app.services.leads.routes", "router"),
        "candidates": ("app.services.candidates.routes", "router"),
    }
    
    def __init__(self):
        self._loaded_services: Dict[str, Any] = {}
        self._loaded_routers: Dict[str, APIRouter] = {}
        self._template_type = self._get_template_type()
        self._template_config = template_configs.get(self._template_type, template_configs[TemplateType.SAAS])
    
    def _get_template_type(self) -> TemplateType:
        """Get template type from settings."""
        template_str = getattr(settings, 'TEMPLATE_TYPE', 'saas').lower()
        try:
            return TemplateType(template_str)
        except ValueError:
            logger.warning(f"Unknown template type '{template_str}', defaulting to 'saas'")
            return TemplateType.SAAS
    
    def get_template_config(self) -> TemplateConfig:
        """Get current template configuration."""
        return self._template_config
    
    def get_template_type(self) -> TemplateType:
        """Get current template type."""
        return self._template_type
    
    def load_router(self, service_name: str) -> Optional[APIRouter]:
        """Load a router for a specific service."""
        if service_name in self._loaded_routers:
            return self._loaded_routers[service_name]
        
        if service_name not in self.SERVICE_MODULES:
            logger.warning(f"Unknown service: {service_name}")
            return None
        
        module_path, router_name = self.SERVICE_MODULES[service_name]
        
        try:
            module = importlib.import_module(module_path)
            router = getattr(module, router_name, None)
            
            if router is None:
                logger.warning(f"Router not found in {module_path}")
                return None
            
            self._loaded_routers[service_name] = router
            logger.info(f"Loaded router: {service_name}")
            return router
            
        except ImportError as e:
            logger.warning(f"Could not import {module_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading router {service_name}: {e}")
            return None
    
    def load_required_routers(self) -> Dict[str, APIRouter]:
        """Load ALL routers for multi-use-case backend (valtunox/valtunox studio style)."""
        routers = {}
        for service_name in self.ALL_SERVICES:
            if service_name not in routers:
                router = self.load_router(service_name)
                if router:
                    routers[service_name] = router
        return routers
    
    def is_service_enabled(self, service_name: str) -> bool:
        """Check if a service is enabled for the current template."""
        return service_name in self._template_config.required_services
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature is enabled for the current template."""
        return self._template_config.feature_flags.get(feature_name, False)
    
    def get_required_services(self) -> List[str]:
        """Get list of required services for current template."""
        return self._template_config.required_services.copy()
    
    def requires_redis(self) -> bool:
        """Check if current template requires Redis."""
        return self._template_config.requires_redis
    
    def requires_celery(self) -> bool:
        """Check if current template requires Celery."""
        return self._template_config.requires_celery
    
    def requires_billing(self) -> bool:
        """Check if current template requires billing."""
        return self._template_config.requires_billing
    
    def requires_kafka(self) -> bool:
        """Check if current template requires Kafka."""
        return self._template_config.requires_kafka
    
    def requires_rabbitmq(self) -> bool:
        """Check if current template requires RabbitMQ."""
        return self._template_config.requires_rabbitmq
    
    def get_template_info(self) -> Dict[str, Any]:
        """Get information about the backend (multi-use-case mode)."""
        return {
            "type": "multi",
            "name": "Multi-Use-Case Backend (valtunox/valtunox studio style)",
            "description": "Single backend serving all templates; project template_type gates feature access",
            "loaded_services": list(self._loaded_routers.keys()),
            "feature_flags": self._template_config.feature_flags,
            "requires_redis": self._template_config.requires_redis,
            "requires_celery": self._template_config.requires_celery,
            "requires_billing": self._template_config.requires_billing,
            "requires_kafka": self._template_config.requires_kafka,
            "requires_rabbitmq": self._template_config.requires_rabbitmq,
        }


# Global service loader instance
_service_loader: Optional[ServiceLoader] = None


def get_service_loader() -> ServiceLoader:
    """Get or create the global service loader instance."""
    global _service_loader
    if _service_loader is None:
        _service_loader = ServiceLoader()
    return _service_loader


def reload_service_loader() -> ServiceLoader:
    """Reload the service loader (useful after settings change)."""
    global _service_loader
    _service_loader = ServiceLoader()
    return _service_loader
