"""
Portfolio Routes

Portfolio projects use blog + saas core. Use /blog and /saas endpoints
with project_id for portfolio-type projects.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


@router.get("/info")
async def portfolio_info():
    """Portfolio service info - use /blog and /saas for portfolio projects."""
    return {
        "service": "portfolio",
        "message": "Portfolio projects use blog and saas endpoints. Use /blog for posts, /saas for tenants.",
        "endpoints": ["/api/v1/blog", "/api/v1/saas"],
    }
