"""
Common Schemas

Shared Pydantic schemas for pagination, responses, etc.
"""

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(default=None, description="Sort field")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.per_page


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    items: List[T]
    total: int
    page: int
    per_page: int
    pages: int

    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        per_page: int,
    ) -> "PaginatedResponse[T]":
        """Create paginated response."""
        pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
        )


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str
    code: Optional[str] = None
    field: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str
    environment: str


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str
    exp: int
    iat: int
    type: str
