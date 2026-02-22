"""CRM schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class LeadBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    status: str = "new"
    score: Optional[int] = None
    source: Optional[str] = None
    notes: Optional[str] = None


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    status: Optional[str] = None
    score: Optional[int] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    assigned_to_id: Optional[str] = None


class LeadResponse(LeadBase):
    id: str
    project_id: str
    assigned_to_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContactBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    notes: Optional[str] = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    notes: Optional[str] = None


class ContactResponse(ContactBase):
    id: str
    project_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DealBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    value: Decimal = Field(0, ge=0)
    stage: str = "lead"
    notes: Optional[str] = None
    contact_id: Optional[str] = None
    pipeline_id: Optional[str] = None


class DealCreate(DealBase):
    pass


class DealUpdate(BaseModel):
    name: Optional[str] = None
    value: Optional[Decimal] = None
    stage: Optional[str] = None
    notes: Optional[str] = None
    contact_id: Optional[str] = None
    pipeline_id: Optional[str] = None
    assigned_to_id: Optional[str] = None


class DealResponse(DealBase):
    id: str
    project_id: str
    assigned_to_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
