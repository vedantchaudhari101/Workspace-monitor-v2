"""API Version 1 Router.

Aggregates all v1 sub-routers and provides a version status endpoint.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.api.v1 import auth, building, occupancy, recommendations, startup, seat, analytics

router = APIRouter()


@router.get("/status", tags=["System"])
async def api_status():
    """Return API v1 status and metadata."""
    return {
        "api_version": "v1",
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(building.router, prefix="/buildings", tags=["Buildings"])
router.include_router(occupancy.router, prefix="/occupancy", tags=["Occupancy"])
router.include_router(seat.router, prefix="/seats", tags=["Seats"])
router.include_router(startup.router, prefix="/startups", tags=["Startups"])
router.include_router(
    recommendations.router, prefix="/recommendations", tags=["Recommendations"]
)
router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
