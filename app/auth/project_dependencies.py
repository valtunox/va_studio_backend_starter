"""
Project type dependencies for multi-use-case backend.

Use these dependencies to guard domain-specific routes so only projects
of the correct template_type can access them.
"""

from typing import List, Optional

from fastapi import Depends, HTTPException, Path, status

from app.orm.project import Project, ProjectTemplateType
from app.orm.user import User
from app.auth.dependencies import get_current_active_user
from app.core.db import get_db
from app.services.projects.service import ProjectService
from sqlalchemy.ext.asyncio import AsyncSession


async def get_project_or_404(
    project_id: str = Path(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Project:
    """Get project by ID; 404 if not found; 403 if user has no access."""
    service = ProjectService(db)
    project = await service.get_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    if not await service.check_access(project, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this project",
        )
    return project


def require_project_template(allowed_types: List[str]):
    """
    Dependency factory: require project to have one of the allowed template types.

    Usage:
        @router.get("/projects/{project_id}/products")
        async def list_products(
            project: Project = Depends(require_project_template(["ecommerce"])),
        ):
            ...
    """

    def _dependency(
        project: Project = Depends(get_project_or_404),
    ) -> Project:
        if project.template_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project type '{project.template_type}' does not support this feature. Required: {allowed_types}",
            )
        return project

    return _dependency


# Convenience dependencies for each domain
RequireEcommerceProject = require_project_template([ProjectTemplateType.ECOMMERCE.value])
RequireBlogProject = require_project_template([ProjectTemplateType.BLOG.value])
RequireCrmProject = require_project_template([ProjectTemplateType.CRM.value])
RequireLeadsProject = require_project_template(
    [ProjectTemplateType.LEADS.value, ProjectTemplateType.CRM.value]
)
RequirePortfolioProject = require_project_template([ProjectTemplateType.PORTFOLIO.value])
RequireSaasProject = require_project_template([ProjectTemplateType.SAAS.value])
RequireErpProject = require_project_template([ProjectTemplateType.ERP.value])
