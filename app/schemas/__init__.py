"""Pydantic schemas for request/response validation."""

from app.schemas.common import (
    PaginatedResponse,
    PaginationParams,
    MessageResponse,
    ErrorResponse,
)
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserInDB,
)
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
)
from app.schemas.billing import (
    SubscriptionResponse,
    PaymentResponse,
    InvoiceResponse,
    CreateCheckoutSession,
)
from app.schemas.blog import (
    PostCreate,
    PostUpdate,
    PostResponse,
    CategoryCreate,
    CategoryResponse,
    TagCreate,
    TagResponse,
)
from app.schemas.notification import (
    NotificationResponse,
    NotificationCreate,
)

__all__ = [
    # Common
    "PaginatedResponse",
    "PaginationParams",
    "MessageResponse",
    "ErrorResponse",
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserInDB",
    # Project
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",
    # Billing
    "SubscriptionResponse",
    "PaymentResponse",
    "InvoiceResponse",
    "CreateCheckoutSession",
    # Blog
    "PostCreate",
    "PostUpdate",
    "PostResponse",
    "CategoryCreate",
    "CategoryResponse",
    "TagCreate",
    "TagResponse",
    # Notification
    "NotificationResponse",
    "NotificationCreate",
]
