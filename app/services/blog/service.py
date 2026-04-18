"""
Blog Service

Business logic for blog posts, categories, and tags.
"""

import re
from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.orm.blog import Post, Category, Tag, PostStatus
from app.orm.user import User
from app.schemas.blog import PostCreate, PostUpdate, CategoryCreate, CategoryUpdate, TagCreate


class BlogService:
    """Blog service for CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _generate_slug(self, text: str) -> str:
        """Generate URL-friendly slug."""
        slug = text.lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        slug = slug.strip("-")
        return f"{slug}-{uuid4().hex[:6]}"

    # Post methods
    async def get_post_by_id(self, post_id: str) -> Optional[Post]:
        """Get post by ID."""
        result = await self.db.execute(
            select(Post).where(Post.id == post_id, Post.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_post_by_slug(self, slug: str) -> Optional[Post]:
        """Get post by slug."""
        result = await self.db.execute(
            select(Post).where(Post.slug == slug, Post.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_posts(
        self,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        category_id: Optional[str] = None,
        author_id: Optional[str] = None,
        published_only: bool = False,
    ) -> tuple[List[Post], int]:
        """Get posts with pagination and filters."""
        query = select(Post).where(Post.is_deleted == False)

        if status:
            query = query.where(Post.status == status)
        if category_id:
            query = query.where(Post.category_id == category_id)
        if author_id:
            query = query.where(Post.author_id == author_id)
        if published_only:
            query = query.where(Post.status == PostStatus.PUBLISHED.value)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        query = query.offset(skip).limit(limit).order_by(Post.created_at.desc())
        result = await self.db.execute(query)
        posts = list(result.scalars().all())

        return posts, total

    async def create_post(self, author: User, post_data: PostCreate) -> Post:
        """Create a new post."""
        slug = post_data.slug or self._generate_slug(post_data.title)

        post = Post(
            title=post_data.title,
            slug=slug,
            excerpt=post_data.excerpt,
            content=post_data.content,
            featured_image=post_data.featured_image,
            status=post_data.status,
            category_id=post_data.category_id,
            author_id=author.id,
            meta_title=post_data.meta_title,
            meta_description=post_data.meta_description,
            meta_keywords=post_data.meta_keywords,
            allow_comments=post_data.allow_comments,
            is_featured=post_data.is_featured,
        )

        if post_data.status == PostStatus.PUBLISHED.value:
            post.published_at = datetime.now(timezone.utc)

        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)

        # Add tags
        if post_data.tag_ids:
            await self._update_post_tags(post, post_data.tag_ids)

        return post

    async def update_post(self, post: Post, post_data: PostUpdate) -> Post:
        """Update post."""
        update_data = post_data.model_dump(exclude_unset=True, exclude={"tag_ids"})

        for field, value in update_data.items():
            setattr(post, field, value)

        # Handle publish status change
        if post_data.status == PostStatus.PUBLISHED.value and not post.published_at:
            post.published_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(post)

        # Update tags if provided
        if post_data.tag_ids is not None:
            await self._update_post_tags(post, post_data.tag_ids)

        return post

    async def _update_post_tags(self, post: Post, tag_ids: List[str]) -> None:
        """Update post tags."""
        result = await self.db.execute(select(Tag).where(Tag.id.in_(tag_ids)))
        tags = list(result.scalars().all())
        post.tags = tags
        await self.db.commit()

    async def delete_post(self, post: Post) -> None:
        """Soft delete post."""
        post.soft_delete()
        await self.db.commit()

    async def publish_post(self, post: Post) -> Post:
        """Publish post."""
        post.status = PostStatus.PUBLISHED.value
        post.published_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(post)
        return post

    async def unpublish_post(self, post: Post) -> Post:
        """Unpublish post (set to draft)."""
        post.status = PostStatus.DRAFT.value
        await self.db.commit()
        await self.db.refresh(post)
        return post

    # Category methods
    async def get_category_by_id(self, category_id: str) -> Optional[Category]:
        """Get category by ID."""
        result = await self.db.execute(
            select(Category).where(Category.id == category_id)
        )
        return result.scalar_one_or_none()

    async def get_category_by_slug(self, slug: str) -> Optional[Category]:
        """Get category by slug."""
        result = await self.db.execute(select(Category).where(Category.slug == slug))
        return result.scalar_one_or_none()

    async def get_categories(
        self,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[Category], int]:
        """Get all categories."""
        query = select(Category)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        query = query.offset(skip).limit(limit).order_by(Category.name)
        result = await self.db.execute(query)
        categories = list(result.scalars().all())

        return categories, total

    async def create_category(self, category_data: CategoryCreate) -> Category:
        """Create category."""
        slug = category_data.slug or self._generate_slug(category_data.name)

        category = Category(
            name=category_data.name,
            slug=slug,
            description=category_data.description,
            parent_id=category_data.parent_id,
            meta_title=category_data.meta_title,
            meta_description=category_data.meta_description,
        )

        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)

        return category

    async def update_category(
        self,
        category: Category,
        category_data: CategoryUpdate,
    ) -> Category:
        """Update category."""
        update_data = category_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(category, field, value)

        await self.db.commit()
        await self.db.refresh(category)

        return category

    async def delete_category(self, category: Category) -> None:
        """Delete category."""
        await self.db.delete(category)
        await self.db.commit()

    # Tag methods
    async def get_tag_by_id(self, tag_id: str) -> Optional[Tag]:
        """Get tag by ID."""
        result = await self.db.execute(select(Tag).where(Tag.id == tag_id))
        return result.scalar_one_or_none()

    async def get_tag_by_slug(self, slug: str) -> Optional[Tag]:
        """Get tag by slug."""
        result = await self.db.execute(select(Tag).where(Tag.slug == slug))
        return result.scalar_one_or_none()

    async def get_tags(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[Tag], int]:
        """Get all tags."""
        query = select(Tag)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        query = query.offset(skip).limit(limit).order_by(Tag.name)
        result = await self.db.execute(query)
        tags = list(result.scalars().all())

        return tags, total

    async def create_tag(self, tag_data: TagCreate) -> Tag:
        """Create tag."""
        slug = tag_data.slug or self._generate_slug(tag_data.name)

        tag = Tag(name=tag_data.name, slug=slug)

        self.db.add(tag)
        await self.db.commit()
        await self.db.refresh(tag)

        return tag

    async def delete_tag(self, tag: Tag) -> None:
        """Delete tag."""
        await self.db.delete(tag)
        await self.db.commit()
