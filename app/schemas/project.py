"""
Project Schemas

Pydantic schemas for project operations.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    """Base project schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)


class ProjectCreate(ProjectBase):
    """Schema for creating a project."""

    slug: Optional[str] = Field(None, max_length=255)
    is_public: bool = False
    template_type: Optional[str] = Field(
        "saas",
        description="Template type: saas, blog, ecommerce, crm, erp, portfolio, etc.",
    )
    settings: Optional[dict] = None


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    slug: Optional[str] = Field(None, max_length=255)
    template_type: Optional[str] = None
    status: Optional[str] = None
    is_public: Optional[bool] = None
    settings: Optional[dict] = None


class ProjectResponse(ProjectBase):
    """Schema for project response."""

    id: str
    slug: str
    template_type: str = "saas"
    status: str
    is_public: bool
    owner_id: str
    created_at: datetime
    updated_at: datetime
    settings: Optional[dict] = None

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """Schema for project list item."""

    id: str
    name: str
    slug: str
    template_type: str = "saas"
    description: Optional[str]
    status: str
    is_public: bool
    created_at: datetime

    model_config = {"from_attributes": True}
