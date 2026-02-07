"""
Project Routes

Endpoints for project management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.orm.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.schemas.common import PaginatedResponse, MessageResponse
from app.auth.dependencies import get_current_active_user, get_optional_user
from app.services.projects.service import ProjectService


router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("/", response_model=PaginatedResponse[ProjectResponse])
async def list_projects(
    page: int = 1,
    per_page: int = 20,
    status: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    List current user's projects.

    Returns paginated list of projects owned by the current user.
    """
    service = ProjectService(db)
    skip = (page - 1) * per_page
    projects, total = await service.get_user_projects(
        user_id=current_user.id,
        skip=skip,
        limit=per_page,
        status=status,
    )

    return PaginatedResponse.create(
        items=projects,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/public", response_model=PaginatedResponse[ProjectResponse])
async def list_public_projects(
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    List public projects.

    Returns paginated list of public projects.
    """
    service = ProjectService(db)
    skip = (page - 1) * per_page
    projects, total = await service.get_public_projects(skip=skip, limit=per_page)

    return PaginatedResponse.create(
        items=projects,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ProjectResponse:
    """
    Create a new project.

    Creates a new project for the current user.
    """
    service = ProjectService(db)

    # Check slug uniqueness if provided
    if project_data.slug:
        existing = await service.get_by_slug(project_data.slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project with this slug already exists",
            )

    project = await service.create(current_user, project_data)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
) -> ProjectResponse:
    """
    Get project by ID.

    Returns project details if user has access.
    """
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
            detail="Access denied",
        )

    return project


@router.get("/slug/{slug}", response_model=ProjectResponse)
async def get_project_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
) -> ProjectResponse:
    """
    Get project by slug.

    Returns project details if user has access.
    """
    service = ProjectService(db)
    project = await service.get_by_slug(slug)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not await service.check_access(project, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ProjectResponse:
    """
    Update project.

    Updates project if user is owner.
    """
    service = ProjectService(db)
    project = await service.get_by_id(project_id)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not await service.check_owner(project, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owner can update",
        )

    # Check slug uniqueness if updating slug
    if project_data.slug and project_data.slug != project.slug:
        existing = await service.get_by_slug(project_data.slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project with this slug already exists",
            )

    return await service.update(project, project_data)


@router.delete("/{project_id}", response_model=MessageResponse)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Delete project.

    Soft deletes project if user is owner.
    """
    service = ProjectService(db)
    project = await service.get_by_id(project_id)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not await service.check_owner(project, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owner can delete",
        )

    await service.delete(project)

    return {"message": "Project deleted successfully", "success": True}


@router.post("/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ProjectResponse:
    """
    Archive project.

    Archives project if user is owner.
    """
    service = ProjectService(db)
    project = await service.get_by_id(project_id)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not await service.check_owner(project, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owner can archive",
        )

    return await service.archive(project)


@router.post("/{project_id}/unarchive", response_model=ProjectResponse)
async def unarchive_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ProjectResponse:
    """
    Unarchive project.

    Unarchives project if user is owner.
    """
    service = ProjectService(db)
    project = await service.get_by_id(project_id)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not await service.check_owner(project, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owner can unarchive",
        )

    return await service.unarchive(project)
