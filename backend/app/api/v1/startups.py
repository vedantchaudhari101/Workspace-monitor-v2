"""Startup management API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, CurrentUser, DbSession, ManagerOrAdmin
from app.schemas.common import MessageResponse
from app.schemas.startup import StartupCreate, StartupResponse, StartupUpdate, StartupUtilization
from app.services.startup_service import StartupService

router = APIRouter()


@router.get("", response_model=list[StartupResponse], summary="List startups")
async def list_startups(
    db: DbSession,
    _user: CurrentUser,
    active_only: bool = Query(default=False),
) -> list[StartupResponse]:
    """Return all tenant startups."""
    return await StartupService(db).list_startups(active_only=active_only)


@router.get("/stats", response_model=list[StartupUtilization], summary="Get stats for all active startups")
async def startups_stats(
    db: DbSession,
    _user: CurrentUser,
    building_id: UUID | None = Query(default=None),
) -> list[StartupUtilization]:
    """Return utilization stats for all active startups."""
    service = StartupService(db)
    startups = await service.list_startups(active_only=True)
    stats = []
    for s in startups:
        stat = await service.get_utilization(UUID(s.id), building_id=building_id)
        stats.append(stat)
    return stats


@router.get("/{startup_id}", response_model=StartupResponse, summary="Get startup")
async def get_startup(
    startup_id: UUID,
    db: DbSession,
    _user: CurrentUser,
) -> StartupResponse:
    """Return a single startup by ID."""
    return await StartupService(db).get_startup(startup_id)


@router.get(
    "/{startup_id}/utilization",
    response_model=StartupUtilization,
    summary="Startup utilization metrics",
)
async def startup_utilization(
    startup_id: UUID,
    db: DbSession,
    _user: CurrentUser,
    building_id: UUID | None = Query(default=None),
) -> StartupUtilization:
    """Return occupancy and revenue leakage metrics for a startup."""
    return await StartupService(db).get_utilization(startup_id, building_id=building_id)


@router.post(
    "",
    response_model=StartupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create startup",
)
async def create_startup(
    db: DbSession,
    _user: ManagerOrAdmin,
    payload: StartupCreate,
) -> StartupResponse:
    """Create a new tenant startup."""
    return await StartupService(db).create_startup(payload)


@router.patch("/{startup_id}", response_model=StartupResponse, summary="Update startup")
async def update_startup(
    startup_id: UUID,
    db: DbSession,
    _user: ManagerOrAdmin,
    payload: StartupUpdate,
) -> StartupResponse:
    """Update an existing startup."""
    return await StartupService(db).update_startup(startup_id, payload)


@router.delete(
    "/{startup_id}",
    response_model=MessageResponse,
    summary="Delete startup",
)
async def delete_startup(
    startup_id: UUID,
    db: DbSession,
    _admin: AdminUser,
) -> MessageResponse:
    """Permanently delete a startup (admin only)."""
    await StartupService(db).delete_startup(startup_id)
    return MessageResponse(message="Startup deleted successfully")
