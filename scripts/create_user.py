#!/usr/bin/env python
"""Create a user in the database via CLI."""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.db import get_async_engine, get_async_session_factory, Base, discover_orm_models
from app.core.security import get_password_hash
from app.core.logger import logger
from app.orm.user import User, UserRole


async def create_user(
    email: str,
    password: str,
    username: str = None,
    full_name: str = None,
    role: str = UserRole.USER.value,
    is_verified: bool = False,
):
    """Create a new user in the database."""
    # Discover all ORM models so tables exist
    discover_orm_models()

    engine = get_async_engine()

    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        # Check if user already exists
        from sqlalchemy import select

        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            logger.error(f"User with email '{email}' already exists (id={existing.id})")
            return None

        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            username=username,
            full_name=full_name,
            role=role,
            is_active=True,
            is_verified=is_verified,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        logger.info(f"User created: {user.email} (id={user.id}, role={user.role})")
        return user


def main():
    parser = argparse.ArgumentParser(description="Create a user in the database")
    parser.add_argument("--email", required=True, help="User email address")
    parser.add_argument("--password", required=True, help="User password")
    parser.add_argument("--username", default=None, help="Username (optional)")
    parser.add_argument("--full-name", default=None, help="Full name (optional)")
    parser.add_argument(
        "--role",
        choices=[r.value for r in UserRole],
        default=UserRole.USER.value,
        help="User role (default: user)",
    )
    parser.add_argument(
        "--verified",
        action="store_true",
        help="Mark user as email-verified",
    )
    args = parser.parse_args()

    user = asyncio.run(
        create_user(
            email=args.email,
            password=args.password,
            username=args.username,
            full_name=args.full_name,
            role=args.role,
            is_verified=args.verified,
        )
    )

    if user:
        print(f"User created successfully!")
        print(f"  ID:       {user.id}")
        print(f"  Email:    {user.email}")
        print(f"  Username: {user.username}")
        print(f"  Role:     {user.role}")
        print(f"  Verified: {user.is_verified}")
    else:
        print("Failed to create user.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
