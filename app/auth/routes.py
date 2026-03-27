"""
Authentication Routes

Endpoints for user authentication and registration.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.settings import settings
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token,
    create_password_reset_token,
    verify_password_reset_token,
    create_email_verification_token,
    verify_email_verification_token,
)
from app.orm.user import User
from app.schemas.user import UserCreate, UserResponse, PasswordReset
from app.schemas.common import TokenResponse, MessageResponse
from app.auth.dependencies import get_current_user, get_current_active_user


router = APIRouter(prefix="/auth", tags=["Authentication"])


from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Login request body."""
    email: str
    password: str


class RefreshRequest(BaseModel):
    """Refresh token request body."""
    refresh_token: str


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Register a new user.

    Creates a new user account with email and password.
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Check if username already exists
    if user_data.username:
        result = await db.execute(select(User).where(User.username == user_data.username))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )

    # Create user
    user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Authenticate user and return JWT tokens.

    Returns access and refresh tokens on successful authentication.
    """
    # Get user by email
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has been deleted",
        )

    # Create tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Refresh access token using refresh token.

    Returns new access and refresh tokens.
    """
    user_id = verify_token(body.refresh_token, "refresh")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Create new tokens
    new_access_token = create_access_token(user.id)
    new_refresh_token = create_refresh_token(user.id)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Logout user.

    Note: JWT tokens are stateless, so this endpoint mainly serves
    as a placeholder. Token blacklisting can be implemented with Redis.
    """
    # In a production environment, you would add the token to a blacklist in Redis
    return {"message": "Successfully logged out", "success": True}


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    email: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Request password reset.

    Sends password reset email if email exists.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    # Always return success to prevent email enumeration
    if user and user.is_active:
        token = create_password_reset_token(user.email)
        # TODO: Send email with reset link
        # background_tasks.add_task(send_password_reset_email, user.email, token)

    return {"message": "If the email exists, a password reset link has been sent", "success": True}


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    data: PasswordReset,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Reset password using token.

    Resets password if token is valid.
    """
    email = verify_password_reset_token(data.token)

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    user.hashed_password = get_password_hash(data.new_password)
    await db.commit()

    return {"message": "Password has been reset successfully", "success": True}


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Verify email address.

    Marks email as verified if token is valid.
    """
    email = verify_email_verification_token(token)

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    if user.is_verified:
        return {"message": "Email is already verified", "success": True}

    user.is_verified = True
    await db.commit()

    return {"message": "Email verified successfully", "success": True}


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Resend email verification.

    Sends new verification email to current user.
    """
    if current_user.is_verified:
        return {"message": "Email is already verified", "success": True}

    token = create_email_verification_token(current_user.email)
    # TODO: Send verification email
    # background_tasks.add_task(send_verification_email, current_user.email, token)

    return {"message": "Verification email sent", "success": True}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Get current user profile.

    Returns the authenticated user's profile.
    """
    return current_user
