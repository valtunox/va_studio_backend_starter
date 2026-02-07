"""
Project Service

Business logic for project management.
"""

import re
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.orm.project import Project, ProjectStatus
from app.orm.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    """Project service for CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _generate_slug(self, name: str) -> str:
        """Generate URL-friendly slug from name."""
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        slug = slug.strip("-")
        # Add unique suffix to avoid collisions
        return f"{slug}-{uuid4().hex[:6]}"

    async def get_by_id(self, project_id: str) -> Optional[Project]:
        """Get project by ID."""
        result = await self.db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Project]:
        """Get project by slug."""
        result = await self.db.execute(
            select(Project).where(
                Project.slug == slug,
                Project.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_projects(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> tuple[List[Project], int]:
        """Get projects for a user with pagination."""
        query = select(Project).where(
            Project.owner_id == user_id,
            Project.is_deleted == False,
        )

        if status:
            query = query.where(Project.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        # Get paginated results
        query = query.offset(skip).limit(limit).order_by(Project.created_at.desc())
        result = await self.db.execute(query)
        projects = list(result.scalars().all())

        return projects, total

    async def get_public_projects(
        self,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[Project], int]:
        """Get public projects with pagination."""
        query = select(Project).where(
            Project.is_public == True,
            Project.is_deleted == False,
            Project.status == ProjectStatus.ACTIVE.value,
        )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        # Get paginated results
        query = query.offset(skip).limit(limit).order_by(Project.created_at.desc())
        result = await self.db.execute(query)
        projects = list(result.scalars().all())

        return projects, total

    async def create(self, owner: User, project_data: ProjectCreate) -> Project:
        """Create a new project."""
        slug = project_data.slug or self._generate_slug(project_data.name)

        project = Project(
            name=project_data.name,
            slug=slug,
            description=project_data.description,
            is_public=project_data.is_public,
            settings=project_data.settings,
            owner_id=owner.id,
        )

        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)

        return project

    async def update(self, project: Project, project_data: ProjectUpdate) -> Project:
        """Update project."""
        update_data = project_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(project, field, value)

        await self.db.commit()
        await self.db.refresh(project)

        return project

    async def delete(self, project: Project) -> None:
        """Soft delete project."""
        project.soft_delete()
        await self.db.commit()

    async def archive(self, project: Project) -> Project:
        """Archive project."""
        project.status = ProjectStatus.ARCHIVED.value
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def unarchive(self, project: Project) -> Project:
        """Unarchive project."""
        project.status = ProjectStatus.ACTIVE.value
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def check_owner(self, project: Project, user: User) -> bool:
        """Check if user is project owner."""
        return project.owner_id == user.id

    async def check_access(self, project: Project, user: Optional[User]) -> bool:
        """Check if user has access to project."""
        if project.is_public:
            return True
        if user and project.owner_id == user.id:
            return True
        return False
