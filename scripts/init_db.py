#!/usr/bin/env python
"""Initialize database with tables."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import engine, Base
from app.core.logger import logger

# Import all models to register them
from app.orm.user import User
from app.orm.project import Project
from app.orm.billing import Subscription, Payment, Invoice
from app.orm.blog import Post, Category, Tag
from app.orm.notification import Notification


async def init_db():
    """Create all database tables."""
    logger.info("Creating database tables...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully!")


async def drop_db():
    """Drop all database tables."""
    logger.info("Dropping database tables...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    logger.info("Database tables dropped!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database initialization")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop all tables before creating",
    )
    args = parser.parse_args()

    if args.drop:
        asyncio.run(drop_db())

    asyncio.run(init_db())
