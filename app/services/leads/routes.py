"""
Leads Routes

Leads projects use CRM endpoints. Use /crm/projects/{project_id}/leads
for lead management when project template_type is 'leads' or 'crm'.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/leads", tags=["Leads"])


@router.get("/info")
async def leads_info():
    """Leads service info - use CRM endpoints for lead management."""
    return {
        "service": "leads",
        "message": "Use /crm/projects/{project_id}/leads for lead CRUD when project type is leads or crm",
        "endpoints": ["/api/v1/crm/projects/{project_id}/leads"],
    }
