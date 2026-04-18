"""
Blog Routes

Endpoints for blog posts, categories, and tags.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.orm.user import User
from app.schemas.blog import (
    PostCreate,
    PostUpdate,
    PostResponse,
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    TagCreate,
    TagResponse,
)
from app.schemas.common import PaginatedResponse, MessageResponse
from app.auth.dependencies import get_current_active_user, get_optional_user, require_admin
from app.services.blog.service import BlogService


router = APIRouter(prefix="/blog", tags=["Blog"])


# Post routes
@router.get("/posts", response_model=PaginatedResponse[PostResponse])
async def list_posts(
    page: int = 1,
    per_page: int = 20,
    status: str = None,
    category_id: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
) -> dict:
    """
    List blog posts.

    Returns published posts for anonymous users, all posts for authenticated users.
    """
    service = BlogService(db)
    skip = (page - 1) * per_page

    published_only = current_user is None
    posts, total = await service.get_posts(
        skip=skip,
        limit=per_page,
        status=status,
        category_id=category_id,
        published_only=published_only,
    )

    return PaginatedResponse.create(
        items=posts,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    post_data: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PostResponse:
    """
    Create a new blog post.

    Creates a new post authored by the current user.
    """
    service = BlogService(db)

    if post_data.slug:
        existing = await service.get_post_by_slug(post_data.slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Post with this slug already exists",
            )

    return await service.create_post(current_user, post_data)


@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
) -> PostResponse:
    """
    Get post by ID.

    Returns post details.
    """
    service = BlogService(db)
    post = await service.get_post_by_id(post_id)

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    # Check if user can view unpublished posts
    if not post.is_published and (not current_user or post.author_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    return post


@router.get("/posts/slug/{slug}", response_model=PostResponse)
async def get_post_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
) -> PostResponse:
    """
    Get post by slug.

    Returns post details.
    """
    service = BlogService(db)
    post = await service.get_post_by_slug(slug)

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    if not post.is_published and (not current_user or post.author_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    return post


@router.patch("/posts/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: str,
    post_data: PostUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PostResponse:
    """
    Update post.

    Updates post if user is author or admin.
    """
    service = BlogService(db)
    post = await service.get_post_by_id(post_id)

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    if post.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this post",
        )

    return await service.update_post(post, post_data)


@router.delete("/posts/{post_id}", response_model=MessageResponse)
async def delete_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Delete post.

    Soft deletes post if user is author or admin.
    """
    service = BlogService(db)
    post = await service.get_post_by_id(post_id)

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    if post.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this post",
        )

    await service.delete_post(post)

    return {"message": "Post deleted successfully", "success": True}


@router.post("/posts/{post_id}/publish", response_model=PostResponse)
async def publish_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PostResponse:
    """
    Publish post.

    Publishes a draft post.
    """
    service = BlogService(db)
    post = await service.get_post_by_id(post_id)

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    if post.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    return await service.publish_post(post)


# Category routes
@router.get("/categories", response_model=PaginatedResponse[CategoryResponse])
async def list_categories(
    page: int = 1,
    per_page: int = 50,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all categories."""
    service = BlogService(db)
    skip = (page - 1) * per_page
    categories, total = await service.get_categories(skip=skip, limit=per_page)

    return PaginatedResponse.create(
        items=categories,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> CategoryResponse:
    """Create category (admin only)."""
    service = BlogService(db)
    return await service.create_category(category_data)


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: str,
    category_data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> CategoryResponse:
    """Update category (admin only)."""
    service = BlogService(db)
    category = await service.get_category_by_id(category_id)

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    return await service.update_category(category, category_data)


@router.delete("/categories/{category_id}", response_model=MessageResponse)
async def delete_category(
    category_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """Delete category (admin only)."""
    service = BlogService(db)
    category = await service.get_category_by_id(category_id)

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    await service.delete_category(category)

    return {"message": "Category deleted", "success": True}


# Tag routes
@router.get("/tags", response_model=PaginatedResponse[TagResponse])
async def list_tags(
    page: int = 1,
    per_page: int = 100,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all tags."""
    service = BlogService(db)
    skip = (page - 1) * per_page
    tags, total = await service.get_tags(skip=skip, limit=per_page)

    return PaginatedResponse.create(
        items=tags,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    tag_data: TagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> TagResponse:
    """Create tag."""
    service = BlogService(db)
    return await service.create_tag(tag_data)


@router.delete("/tags/{tag_id}", response_model=MessageResponse)
async def delete_tag(
    tag_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """Delete tag (admin only)."""
    service = BlogService(db)
    tag = await service.get_tag_by_id(tag_id)

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    await service.delete_tag(tag)

    return {"message": "Tag deleted", "success": True}
