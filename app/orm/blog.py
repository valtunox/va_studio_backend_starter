"""
Blog/CMS Models

Posts, categories, and tags for content management.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional
from uuid import uuid4

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Table, Column, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.orm.base import Base, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.orm.user import User


class PostStatus(str, Enum):
    """Post status enumeration."""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# Association table for post-tag relationship
post_tags = Table(
    "post_tags",
    Base.metadata,
    Column(
        "post_id",
        UUID(as_uuid=False),
        ForeignKey("posts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        UUID(as_uuid=False),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Category(Base, TimestampMixin):
    """Category model."""

    __tablename__ = "categories"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Basic info
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # SEO
    meta_title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    meta_description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Parent category (for nested categories)
    parent_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    posts: Mapped[List["Post"]] = relationship(
        "Post",
        back_populates="category",
        lazy="selectin",
    )
    children: Mapped[List["Category"]] = relationship(
        "Category",
        back_populates="parent",
        lazy="selectin",
    )
    parent: Mapped[Optional["Category"]] = relationship(
        "Category",
        back_populates="children",
        remote_side=[id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Category {self.name}>"


class Tag(Base, TimestampMixin):
    """Tag model."""

    __tablename__ = "tags"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Basic info
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )

    # Relationships
    posts: Mapped[List["Post"]] = relationship(
        "Post",
        secondary=post_tags,
        back_populates="tags",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Tag {self.name}>"


class Post(Base, TimestampMixin, SoftDeleteMixin):
    """Blog post model."""

    __tablename__ = "posts"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Basic info
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    excerpt: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Media
    featured_image: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=PostStatus.DRAFT.value,
        nullable=False,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # SEO
    meta_title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    meta_description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    meta_keywords: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Settings
    allow_comments: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Metadata
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=True,
    )

    # Author
    author_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Category
    category_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    author: Mapped["User"] = relationship(
        "User",
        lazy="selectin",
    )
    category: Mapped[Optional["Category"]] = relationship(
        "Category",
        back_populates="posts",
        lazy="selectin",
    )
    tags: Mapped[List["Tag"]] = relationship(
        "Tag",
        secondary=post_tags,
        back_populates="posts",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Post {self.title}>"

    @property
    def is_published(self) -> bool:
        """Check if post is published."""
        return self.status == PostStatus.PUBLISHED.value
