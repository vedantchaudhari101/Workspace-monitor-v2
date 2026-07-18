"""Building API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.building import BuildingDetail, BuildingSummary, BuildingUtilization
from app.services.building_service import BuildingService

router = APIRouter()


@router.get("", response_model=list[BuildingSummary], summary="List buildings")
async def list_buildings(db: DbSession, _user: CurrentUser) -> list[BuildingSummary]:
    """Return all active buildings."""
    return await BuildingService(db).list_buildings()


@router.get("/{building_id}", response_model=BuildingDetail, summary="Get building")
async def get_building(
    building_id: UUID,
    db: DbSession,
    _user: CurrentUser,
) -> BuildingDetail:
    """Return building details including floors."""
    return await BuildingService(db).get_building(building_id)


@router.get(
    "/{building_id}/utilization",
    response_model=BuildingUtilization,
    summary="Building utilization summary",
)
async def building_utilization(
    building_id: UUID,
    db: DbSession,
    _user: CurrentUser,
) -> BuildingUtilization:
    """Return live occupancy metrics for a building."""
    return await BuildingService(db).get_utilization(building_id)
