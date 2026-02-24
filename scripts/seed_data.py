#!/usr/bin/env python
"""Seed database with sample data."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.db import get_async_session_factory
from app.core.security import get_password_hash
from app.core.logger import logger
from app.orm.user import User, UserRole
from app.orm.project import Project
from app.orm.blog import Category, Tag, Post
from app.orm.billing import Subscription, SubscriptionPlan


async def seed_users(db):
    """Create sample users."""
    logger.info("Creating sample users...")

    users = [
        {
            "email": "admin@example.com",
            "username": "admin",
            "full_name": "Admin User",
            "hashed_password": get_password_hash("Admin123!"),
            "role": UserRole.ADMIN.value,
            "is_verified": True,
        },
        {
            "email": "user@example.com",
            "username": "testuser",
            "full_name": "Test User",
            "hashed_password": get_password_hash("User123!"),
            "role": UserRole.USER.value,
            "is_verified": True,
        },
    ]

    created_users = []
    for user_data in users:
        user = User(**user_data)
        db.add(user)
        created_users.append(user)

    await db.commit()

    for user in created_users:
        await db.refresh(user)

    logger.info(f"Created {len(created_users)} users")
    return created_users


async def seed_projects(db, users):
    """Create sample projects."""
    logger.info("Creating sample projects...")

    projects = [
        {
            "name": "My First Project",
            "slug": "my-first-project",
            "description": "A sample project for demonstration",
            "owner_id": users[1].id,
            "is_public": True,
        },
        {
            "name": "Private Project",
            "slug": "private-project",
            "description": "A private project",
            "owner_id": users[1].id,
            "is_public": False,
        },
    ]

    created_projects = []
    for project_data in projects:
        project = Project(**project_data)
        db.add(project)
        created_projects.append(project)

    await db.commit()
    logger.info(f"Created {len(created_projects)} projects")
    return created_projects


async def seed_blog(db, users):
    """Create sample blog content."""
    logger.info("Creating sample blog content...")

    # Categories
    categories = [
        {"name": "Technology", "slug": "technology", "description": "Tech articles"},
        {"name": "Business", "slug": "business", "description": "Business insights"},
        {"name": "Tutorial", "slug": "tutorial", "description": "How-to guides"},
    ]

    created_categories = []
    for cat_data in categories:
        category = Category(**cat_data)
        db.add(category)
        created_categories.append(category)

    await db.commit()

    # Tags
    tags = [
        {"name": "Python", "slug": "python"},
        {"name": "FastAPI", "slug": "fastapi"},
        {"name": "Docker", "slug": "docker"},
        {"name": "SaaS", "slug": "saas"},
    ]

    created_tags = []
    for tag_data in tags:
        tag = Tag(**tag_data)
        db.add(tag)
        created_tags.append(tag)

    await db.commit()

    # Posts
    posts = [
        {
            "title": "Getting Started with VA Studio",
            "slug": "getting-started-va-studio",
            "excerpt": "Learn how to get started with VA Studio Backend",
            "content": "This is a comprehensive guide to getting started with VA Studio Backend...",
            "author_id": users[0].id,
            "category_id": created_categories[2].id,
            "status": "published",
            "is_featured": True,
        },
        {
            "title": "Building SaaS Applications",
            "slug": "building-saas-applications",
            "excerpt": "Best practices for building SaaS applications",
            "content": "In this article, we explore best practices for building SaaS applications...",
            "author_id": users[0].id,
            "category_id": created_categories[1].id,
            "status": "published",
        },
    ]

    for post_data in posts:
        post = Post(**post_data)
        post.tags = created_tags[:2]
        db.add(post)

    await db.commit()
    logger.info("Created blog content")


async def seed_subscriptions(db, users):
    """Create sample subscriptions."""
    logger.info("Creating sample subscriptions...")

    subscriptions = [
        {
            "user_id": users[0].id,
            "plan": SubscriptionPlan.ENTERPRISE.value,
            "status": "active",
        },
        {
            "user_id": users[1].id,
            "plan": SubscriptionPlan.FREE.value,
            "status": "active",
        },
    ]

    for sub_data in subscriptions:
        subscription = Subscription(**sub_data)
        db.add(subscription)

    await db.commit()
    logger.info("Created subscriptions")


async def main():
    """Run all seed functions."""
    logger.info("Starting database seeding...")

    session_factory = get_async_session_factory()
    async with session_factory() as db:
        try:
            users = await seed_users(db)
            await seed_projects(db, users)
            await seed_blog(db, users)
            await seed_subscriptions(db, users)

            logger.info("Database seeding completed successfully!")
            logger.info("")
            logger.info("Sample credentials:")
            logger.info("  Admin: admin@example.com / Admin123!")
            logger.info("  User:  user@example.com / User123!")

        except Exception as e:
            logger.error(f"Error seeding database: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
