"""
Candidates/cloudsystem Routes

Stub for future implementation (candidates, jobs, interviews, pipeline).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/candidates", tags=["Candidates"])


@router.get("/info")
async def candidates_info():
    """Candidates service info - stub for future implementation."""
    return {
        "service": "candidates",
        "message": "cloudsystem (candidates, jobs, interviews) - coming soon",
        "status": "stub",
    }
