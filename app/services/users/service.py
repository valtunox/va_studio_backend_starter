"""
User Service

Business logic for user management.
"""

from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.orm.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password


class UserService:
    """User service for CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email, User.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        result = await self.db.execute(
            select(User).where(User.username == username, User.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
        is_active: Optional[bool] = None,
    ) -> tuple[List[User], int]:
        """Get all users with pagination."""
        query = select(User).where(User.is_deleted == False)

        if is_active is not None:
            query = query.where(User.is_active == is_active)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        # Get paginated results
        query = query.offset(skip).limit(limit).order_by(User.created_at.desc())
        result = await self.db.execute(query)
        users = list(result.scalars().all())

        return users, total

    async def create(self, user_data: UserCreate) -> User:
        """Create a new user."""
        user = User(
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            hashed_password=get_password_hash(user_data.password),
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def update(self, user: User, user_data: UserUpdate) -> User:
        """Update user."""
        update_data = user_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(user, field, value)

        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def update_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Update user password."""
        if not verify_password(current_password, user.hashed_password):
            return False

        user.hashed_password = get_password_hash(new_password)
        await self.db.commit()

        return True

    async def delete(self, user: User) -> None:
        """Soft delete user."""
        user.soft_delete()
        await self.db.commit()

    async def activate(self, user: User) -> User:
        """Activate user."""
        user.is_active = True
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def deactivate(self, user: User) -> User:
        """Deactivate user."""
        user.is_active = False
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def verify_email(self, user: User) -> User:
        """Mark user email as verified."""
        user.is_verified = True
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def set_role(self, user: User, role: str) -> User:
        """Set user role."""
        user.role = role
        await self.db.commit()
        await self.db.refresh(user)
        return user
