"""
CRM Routes

Leads, contacts, deals - scoped by project_id. Use require_project_template
to ensure only CRM/leads projects can access these endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.orm.crm import Lead, Contact, Deal
from app.orm.project import Project
from app.schemas.crm import (
    LeadCreate,
    LeadUpdate,
    LeadResponse,
    ContactCreate,
    ContactUpdate,
    ContactResponse,
    DealCreate,
    DealUpdate,
    DealResponse,
)
from app.schemas.common import PaginatedResponse
from app.auth.project_dependencies import (
    RequireCrmProject,
    RequireLeadsProject,
)

router = APIRouter(prefix="/crm", tags=["CRM"])


def _require_crm_or_leads(project: Project = Depends(RequireLeadsProject)):
    """Accept both crm and leads project types."""
    return project


# --- Leads ---
@router.get(
    "/projects/{project_id}/leads",
    response_model=PaginatedResponse[LeadResponse],
)
async def list_leads(
    project_id: str,
    page: int = 1,
    per_page: int = 20,
    status: str = None,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(_require_crm_or_leads),
):
    """List leads for a CRM/leads project."""
    skip = (page - 1) * per_page
    query = select(Lead).where(
        Lead.project_id == project_id,
        Lead.is_deleted == False,
    )
    if status:
        query = query.where(Lead.status == status)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(Lead.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post(
    "/projects/{project_id}/leads",
    response_model=LeadResponse,
    status_code=201,
)
async def create_lead(
    project_id: str,
    data: LeadCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(_require_crm_or_leads),
):
    """Create a lead."""
    lead = Lead(
        project_id=project_id,
        name=data.name,
        email=data.email,
        phone=data.phone,
        company=data.company,
        status=data.status,
        score=data.score,
        source=data.source,
        notes=data.notes,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


@router.get(
    "/projects/{project_id}/leads/{lead_id}",
    response_model=LeadResponse,
)
async def get_lead(
    project_id: str,
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(_require_crm_or_leads),
):
    """Get a lead by ID."""
    result = await db.execute(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.project_id == project_id,
            Lead.is_deleted == False,
        )
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.patch(
    "/projects/{project_id}/leads/{lead_id}",
    response_model=LeadResponse,
)
async def update_lead(
    project_id: str,
    lead_id: str,
    data: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(_require_crm_or_leads),
):
    """Update a lead."""
    result = await db.execute(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.project_id == project_id,
            Lead.is_deleted == False,
        )
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(lead, k, v)
    await db.commit()
    await db.refresh(lead)
    return lead


@router.delete("/projects/{project_id}/leads/{lead_id}")
async def delete_lead(
    project_id: str,
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(_require_crm_or_leads),
):
    """Soft-delete a lead."""
    result = await db.execute(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.project_id == project_id,
            Lead.is_deleted == False,
        )
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.soft_delete()
    await db.commit()
    return {"message": "Lead deleted"}


# --- Contacts ---
@router.get(
    "/projects/{project_id}/contacts",
    response_model=PaginatedResponse[ContactResponse],
)
async def list_contacts(
    project_id: str,
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireCrmProject),
):
    """List contacts for a CRM project."""
    skip = (page - 1) * per_page
    query = select(Contact).where(
        Contact.project_id == project_id,
        Contact.is_deleted == False,
    )
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(Contact.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post(
    "/projects/{project_id}/contacts",
    response_model=ContactResponse,
    status_code=201,
)
async def create_contact(
    project_id: str,
    data: ContactCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireCrmProject),
):
    """Create a contact."""
    contact = Contact(
        project_id=project_id,
        name=data.name,
        email=data.email,
        phone=data.phone,
        company=data.company,
        title=data.title,
        notes=data.notes,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


@router.get(
    "/projects/{project_id}/contacts/{contact_id}",
    response_model=ContactResponse,
)
async def get_contact(
    project_id: str,
    contact_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireCrmProject),
):
    """Get a contact by ID."""
    result = await db.execute(
        select(Contact).where(
            Contact.id == contact_id,
            Contact.project_id == project_id,
            Contact.is_deleted == False,
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.patch(
    "/projects/{project_id}/contacts/{contact_id}",
    response_model=ContactResponse,
)
async def update_contact(
    project_id: str,
    contact_id: str,
    data: ContactUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireCrmProject),
):
    """Update a contact."""
    result = await db.execute(
        select(Contact).where(
            Contact.id == contact_id,
            Contact.project_id == project_id,
            Contact.is_deleted == False,
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(contact, k, v)
    await db.commit()
    await db.refresh(contact)
    return contact


@router.delete("/projects/{project_id}/contacts/{contact_id}")
async def delete_contact(
    project_id: str,
    contact_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireCrmProject),
):
    """Soft-delete a contact."""
    result = await db.execute(
        select(Contact).where(
            Contact.id == contact_id,
            Contact.project_id == project_id,
            Contact.is_deleted == False,
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact.soft_delete()
    await db.commit()
    return {"message": "Contact deleted"}


# --- Deals ---
@router.get(
    "/projects/{project_id}/deals",
    response_model=PaginatedResponse[DealResponse],
)
async def list_deals(
    project_id: str,
    page: int = 1,
    per_page: int = 20,
    stage: str = None,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireCrmProject),
):
    """List deals for a CRM project."""
    skip = (page - 1) * per_page
    query = select(Deal).where(
        Deal.project_id == project_id,
        Deal.is_deleted == False,
    )
    if stage:
        query = query.where(Deal.stage == stage)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(Deal.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post(
    "/projects/{project_id}/deals",
    response_model=DealResponse,
    status_code=201,
)
async def create_deal(
    project_id: str,
    data: DealCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireCrmProject),
):
    """Create a deal."""
    deal = Deal(
        project_id=project_id,
        name=data.name,
        value=data.value,
        stage=data.stage,
        notes=data.notes,
        contact_id=data.contact_id,
        pipeline_id=data.pipeline_id,
    )
    db.add(deal)
    await db.commit()
    await db.refresh(deal)
    return deal


@router.get(
    "/projects/{project_id}/deals/{deal_id}",
    response_model=DealResponse,
)
async def get_deal(
    project_id: str,
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireCrmProject),
):
    """Get a deal by ID."""
    result = await db.execute(
        select(Deal).where(
            Deal.id == deal_id,
            Deal.project_id == project_id,
            Deal.is_deleted == False,
        )
    )
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    return deal


@router.patch(
    "/projects/{project_id}/deals/{deal_id}",
    response_model=DealResponse,
)
async def update_deal(
    project_id: str,
    deal_id: str,
    data: DealUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireCrmProject),
):
    """Update a deal."""
    result = await db.execute(
        select(Deal).where(
            Deal.id == deal_id,
            Deal.project_id == project_id,
            Deal.is_deleted == False,
        )
    )
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(deal, k, v)
    await db.commit()
    await db.refresh(deal)
    return deal


@router.delete("/projects/{project_id}/deals/{deal_id}")
async def delete_deal(
    project_id: str,
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireCrmProject),
):
    """Soft-delete a deal."""
    result = await db.execute(
        select(Deal).where(
            Deal.id == deal_id,
            Deal.project_id == project_id,
            Deal.is_deleted == False,
        )
    )
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    deal.soft_delete()
    await db.commit()
    return {"message": "Deal deleted"}
