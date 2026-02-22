"""
ERP Routes

Stub for future ERP implementation (inventory, HR, finance modules).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/erp", tags=["ERP"])


@router.get("/info")
async def erp_info():
    """ERP service info - stub for future implementation."""
    return {
        "service": "erp",
        "message": "ERP modules (inventory, HR, finance) - coming soon",
        "status": "stub",
    }
