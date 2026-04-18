"""CRM schemas — leads, contacts, deals, pipelines, activities, tasks."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Lead
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Contact
# ---------------------------------------------------------------------------

class ContactBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    status: str = "lead"
    value: Decimal = Decimal("0")
    avatar_url: Optional[str] = None
    notes: Optional[str] = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    status: Optional[str] = None
    value: Optional[Decimal] = None
    avatar_url: Optional[str] = None
    notes: Optional[str] = None


class ContactResponse(ContactBase):
    id: str
    project_id: str
    last_contact_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class PipelineBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., max_length=100)
    stages: Optional[dict] = None


class PipelineCreate(PipelineBase):
    pass


class PipelineUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    stages: Optional[dict] = None


class PipelineResponse(PipelineBase):
    id: str
    project_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Deal
# ---------------------------------------------------------------------------

class DealBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    company: Optional[str] = None
    value: Decimal = Field(Decimal("0"), ge=0)
    stage: str = "lead"
    probability: int = Field(0, ge=0, le=100)
    days_in_stage: int = 0
    expected_close_date: Optional[datetime] = None
    loss_reason: Optional[str] = None
    notes: Optional[str] = None
    contact_id: Optional[str] = None
    pipeline_id: Optional[str] = None


class DealCreate(DealBase):
    pass


class DealUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    value: Optional[Decimal] = None
    stage: Optional[str] = None
    probability: Optional[int] = Field(None, ge=0, le=100)
    days_in_stage: Optional[int] = None
    expected_close_date: Optional[datetime] = None
    loss_reason: Optional[str] = None
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


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------

class ActivityCreate(BaseModel):
    type: str = "note"
    description: str = Field(..., min_length=1)
    related_type: Optional[str] = None
    related_id: Optional[str] = None


class ActivityResponse(BaseModel):
    id: str
    project_id: str
    user_id: Optional[str] = None
    type: str
    description: str
    related_type: Optional[str] = None
    related_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# CRM Task
# ---------------------------------------------------------------------------

class CrmTaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    priority: str = "medium"
    due_date: Optional[datetime] = None
    assignee_name: Optional[str] = None
    deal_id: Optional[str] = None
    contact_id: Optional[str] = None


class CrmTaskCreate(CrmTaskBase):
    pass


class CrmTaskUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    priority: Optional[str] = None
    is_done: Optional[bool] = None
    due_date: Optional[datetime] = None
    assigned_to_id: Optional[str] = None
    assignee_name: Optional[str] = None
    deal_id: Optional[str] = None
    contact_id: Optional[str] = None


class CrmTaskResponse(CrmTaskBase):
    id: str
    project_id: str
    is_done: bool = False
    completed_at: Optional[datetime] = None
    assigned_to_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
