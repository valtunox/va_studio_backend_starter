"""
Blog Schemas

Pydantic schemas for blog posts, categories, and tags.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# Tag schemas
class TagBase(BaseModel):
    """Base tag schema."""

    name: str = Field(..., min_length=1, max_length=50)


class TagCreate(TagBase):
    """Schema for creating a tag."""

    slug: Optional[str] = Field(None, max_length=50)


class TagResponse(TagBase):
    """Schema for tag response."""

    id: str
    slug: str
    created_at: datetime

    model_config = {"from_attributes": True}


# Category schemas
class CategoryBase(BaseModel):
    """Base category schema."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class CategoryCreate(CategoryBase):
    """Schema for creating a category."""

    slug: Optional[str] = Field(None, max_length=100)
    parent_id: Optional[str] = None
    meta_title: Optional[str] = Field(None, max_length=255)
    meta_description: Optional[str] = Field(None, max_length=500)


class CategoryUpdate(BaseModel):
    """Schema for updating a category."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    slug: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    parent_id: Optional[str] = None
    meta_title: Optional[str] = Field(None, max_length=255)
    meta_description: Optional[str] = Field(None, max_length=500)


class CategoryResponse(CategoryBase):
    """Schema for category response."""

    id: str
    slug: str
    parent_id: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# Post schemas
class PostBase(BaseModel):
    """Base post schema."""

    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class PostCreate(PostBase):
    """Schema for creating a post."""

    slug: Optional[str] = Field(None, max_length=255)
    excerpt: Optional[str] = Field(None, max_length=500)
    featured_image: Optional[str] = Field(None, max_length=500)
    status: str = "draft"
    category_id: Optional[str] = None
    tag_ids: List[str] = []
    meta_title: Optional[str] = Field(None, max_length=255)
    meta_description: Optional[str] = Field(None, max_length=500)
    meta_keywords: Optional[str] = Field(None, max_length=255)
    allow_comments: bool = True
    is_featured: bool = False


class PostUpdate(BaseModel):
    """Schema for updating a post."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    slug: Optional[str] = Field(None, max_length=255)
    excerpt: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = None
    featured_image: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = None
    category_id: Optional[str] = None
    tag_ids: Optional[List[str]] = None
    meta_title: Optional[str] = Field(None, max_length=255)
    meta_description: Optional[str] = Field(None, max_length=500)
    meta_keywords: Optional[str] = Field(None, max_length=255)
    allow_comments: Optional[bool] = None
    is_featured: Optional[bool] = None


class PostResponse(PostBase):
    """Schema for post response."""

    id: str
    slug: str
    excerpt: Optional[str] = None
    featured_image: Optional[str] = None
    status: str
    published_at: Optional[datetime] = None
    author_id: str
    category_id: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None
    allow_comments: bool
    is_featured: bool
    created_at: datetime
    updated_at: datetime
    tags: List[TagResponse] = []
    category: Optional[CategoryResponse] = None

    model_config = {"from_attributes": True}


class PostListResponse(BaseModel):
    """Schema for post list item."""

    id: str
    title: str
    slug: str
    excerpt: Optional[str] = None
    featured_image: Optional[str] = None
    status: str
    published_at: Optional[datetime] = None
    author_id: str
    is_featured: bool
    created_at: datetime

    model_config = {"from_attributes": True}
