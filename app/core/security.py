"""
Security Utilities

JWT token handling, password hashing, and authentication utilities.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


# Password hashing context with Argon2
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)


def create_access_token(
    subject: Union[str, int],
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[dict] = None,
) -> str:
    """
    Create JWT access token.

    Args:
        subject: Token subject (typically user ID)
        expires_delta: Custom expiration time
        additional_claims: Extra claims to include in token

    Returns:
        Encoded JWT token
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }

    if additional_claims:
        to_encode.update(additional_claims)

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(
    subject: Union[str, int],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create JWT refresh token.

    Args:
        subject: Token subject (typically user ID)
        expires_delta: Custom expiration time

    Returns:
        Encoded JWT refresh token
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    }

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """
    Decode and validate JWT token.

    Args:
        token: JWT token to decode

    Returns:
        Token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None


def verify_token(token: str, token_type: str = "access") -> Optional[str]:
    """
    Verify JWT token and extract subject.

    Args:
        token: JWT token to verify
        token_type: Expected token type ("access" or "refresh")

    Returns:
        Token subject (user ID) if valid, None otherwise
    """
    payload = decode_token(token)

    if payload is None:
        return None

    if payload.get("type") != token_type:
        return None

    return payload.get("sub")


def create_password_reset_token(email: str) -> str:
    """Create password reset token."""
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    to_encode = {
        "sub": email,
        "exp": expire,
        "type": "password_reset",
    }
    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def verify_password_reset_token(token: str) -> Optional[str]:
    """Verify password reset token and return email."""
    payload = decode_token(token)

    if payload is None:
        return None

    if payload.get("type") != "password_reset":
        return None

    return payload.get("sub")


def create_email_verification_token(email: str) -> str:
    """Create email verification token."""
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode = {
        "sub": email,
        "exp": expire,
        "type": "email_verification",
    }
    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def verify_email_verification_token(token: str) -> Optional[str]:
    """Verify email verification token and return email."""
    payload = decode_token(token)

    if payload is None:
        return None

    if payload.get("type") != "email_verification":
        return None

    return payload.get("sub")


def validate_api_key(api_key: str) -> bool:
    """Validate API key."""
    return api_key in settings.API_KEYS
