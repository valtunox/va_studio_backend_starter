"""
User Routes

Endpoints for user management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.orm.user import User
from app.schemas.user import UserResponse, UserUpdate, PasswordChange
from app.schemas.common import PaginatedResponse, MessageResponse
from app.auth.dependencies import get_current_active_user, require_admin
from app.services.users.service import UserService


router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=PaginatedResponse[UserResponse])
async def list_users(
    page: int = 1,
    per_page: int = 20,
    is_active: bool = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """
    List all users (admin only).

    Returns paginated list of users.
    """
    service = UserService(db)
    skip = (page - 1) * per_page
    users, total = await service.get_all(skip=skip, limit=per_page, is_active=is_active)

    return PaginatedResponse.create(
        items=users,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Get current user profile.

    Returns the authenticated user's profile.
    """
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Update current user profile.

    Updates the authenticated user's profile.
    """
    service = UserService(db)

    # Check for email uniqueness if updating email
    if user_data.email and user_data.email != current_user.email:
        existing = await service.get_by_email(user_data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    # Check for username uniqueness if updating username
    if user_data.username and user_data.username != current_user.username:
        existing = await service.get_by_username(user_data.username)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )

    return await service.update(current_user, user_data)


@router.post("/me/change-password", response_model=MessageResponse)
async def change_password(
    password_data: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Change current user password.

    Changes password if current password is correct.
    """
    service = UserService(db)
    success = await service.update_password(
        current_user,
        password_data.current_password,
        password_data.new_password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    return {"message": "Password changed successfully", "success": True}


@router.delete("/me", response_model=MessageResponse)
async def delete_current_user(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Delete current user account.

    Soft deletes the authenticated user's account.
    """
    service = UserService(db)
    await service.delete(current_user)

    return {"message": "Account deleted successfully", "success": True}


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> User:
    """
    Get user by ID (admin only).

    Returns user details.
    """
    service = UserService(db)
    user = await service.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> User:
    """
    Update user by ID (admin only).

    Updates user details.
    """
    service = UserService(db)
    user = await service.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return await service.update(user, user_data)


@router.post("/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> User:
    """
    Activate user (admin only).

    Activates a deactivated user account.
    """
    service = UserService(db)
    user = await service.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return await service.activate(user)


@router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> User:
    """
    Deactivate user (admin only).

    Deactivates a user account.
    """
    service = UserService(db)
    user = await service.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    return await service.deactivate(user)
