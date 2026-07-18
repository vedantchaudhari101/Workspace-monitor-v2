"""Building, Floor, and Zone API routes."""

from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.exceptions import NotFoundError
from app.models.building import Building
from app.models.floor import Floor
from app.models.zone import Zone
from app.schemas.building import (
    BuildingCreate,
    BuildingDetail,
    BuildingSummary,
    BuildingUpdate,
    BuildingUtilization,
    FloorCreate,
    FloorResponse,
    FloorUpdate,
    ZoneCreate,
    ZoneResponse,
    ZoneUpdate,
)
from app.services.building_service import BuildingService

router = APIRouter()

# ── Buildings CRUD ──────────────────────────────────────────────────────────

@router.post("", response_model=BuildingSummary, status_code=status.HTTP_201_CREATED, summary="Create building")
async def create_building(db: DbSession, payload: BuildingCreate, _user: CurrentUser) -> BuildingSummary:
    """Create a new physical building."""
    building = Building(
        name=payload.name,
        address=payload.address,
        city=payload.city,
        total_capacity=payload.total_capacity,
        is_active=payload.is_active,
    )
    db.add(building)
    await db.flush()
    await db.refresh(building)
    return BuildingSummary.model_validate(building)


@router.get("", response_model=list[BuildingSummary], summary="List buildings")
async def list_buildings(db: DbSession, _user: CurrentUser) -> list[BuildingSummary]:
    """Return all active buildings."""
    return await BuildingService(db).list_buildings()


@router.get("/{building_id}", response_model=BuildingDetail, summary="Get building")
async def get_building(building_id: UUID, db: DbSession, _user: CurrentUser) -> BuildingDetail:
    """Return building details including floors."""
    return await BuildingService(db).get_building(building_id)


@router.put("/{building_id}", response_model=BuildingSummary, summary="Update building")
async def update_building(
    building_id: UUID, db: DbSession, payload: BuildingUpdate, _user: CurrentUser
) -> BuildingSummary:
    """Update building details."""
    building = await db.get(Building, building_id)
    if not building:
        raise NotFoundError("Building", str(building_id))
    
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(building, field, val)
        
    await db.flush()
    await db.refresh(building)
    return BuildingSummary.model_validate(building)


@router.delete("/{building_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete building")
async def delete_building(building_id: UUID, db: DbSession, _user: CurrentUser) -> None:
    """Delete a building."""
    building = await db.get(Building, building_id)
    if not building:
        raise NotFoundError("Building", str(building_id))
    await db.delete(building)
    await db.flush()


@router.get("/{building_id}/utilization", response_model=BuildingUtilization, summary="Building utilization summary")
async def building_utilization(building_id: UUID, db: DbSession, _user: CurrentUser) -> BuildingUtilization:
    """Return live occupancy metrics for a building."""
    return await BuildingService(db).get_utilization(building_id)


# ── Floors CRUD ─────────────────────────────────────────────────────────────

@router.post("/floors", response_model=FloorResponse, status_code=status.HTTP_201_CREATED, summary="Create floor")
async def create_floor(db: DbSession, payload: FloorCreate, _user: CurrentUser) -> FloorResponse:
    """Create a new floor within a building."""
    building = await db.get(Building, payload.building_id)
    if not building:
        raise NotFoundError("Building", str(payload.building_id))
        
    floor = Floor(
        building_id=payload.building_id,
        name=payload.name,
        floor_number=payload.floor_number,
        total_capacity=payload.total_capacity,
        is_active=payload.is_active,
    )
    db.add(floor)
    await db.flush()
    await db.refresh(floor)
    return FloorResponse.model_validate(floor)


@router.get("/floors/{floor_id}", response_model=FloorResponse, summary="Get floor")
async def get_floor(floor_id: UUID, db: DbSession, _user: CurrentUser) -> FloorResponse:
    """Return details of a specific floor."""
    floor = await db.get(Floor, floor_id)
    if not floor:
        raise NotFoundError("Floor", str(floor_id))
    return FloorResponse.model_validate(floor)


@router.put("/floors/{floor_id}", response_model=FloorResponse, summary="Update floor")
async def update_floor(
    floor_id: UUID, db: DbSession, payload: FloorUpdate, _user: CurrentUser
) -> FloorResponse:
    """Update floor details."""
    floor = await db.get(Floor, floor_id)
    if not floor:
        raise NotFoundError("Floor", str(floor_id))
        
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(floor, field, val)
        
    await db.flush()
    await db.refresh(floor)
    return FloorResponse.model_validate(floor)


@router.delete("/floors/{floor_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete floor")
async def delete_floor(floor_id: UUID, db: DbSession, _user: CurrentUser) -> None:
    """Delete a floor."""
    floor = await db.get(Floor, floor_id)
    if not floor:
        raise NotFoundError("Floor", str(floor_id))
    await db.delete(floor)
    await db.flush()


# ── Zones CRUD ──────────────────────────────────────────────────────────────

@router.post("/zones", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED, summary="Create zone")
async def create_zone(db: DbSession, payload: ZoneCreate, _user: CurrentUser) -> ZoneResponse:
    """Create a new zone within a floor."""
    floor = await db.get(Floor, payload.floor_id)
    if not floor:
        raise NotFoundError("Floor", str(payload.floor_id))
        
    zone = Zone(
        floor_id=payload.floor_id,
        name=payload.name,
        zone_type=payload.zone_type,
        total_capacity=payload.total_capacity,
        is_active=payload.is_active,
    )
    db.add(zone)
    await db.flush()
    await db.refresh(zone)
    return ZoneResponse.model_validate(zone)


@router.get("/zones/{zone_id}", response_model=ZoneResponse, summary="Get zone")
async def get_zone(zone_id: UUID, db: DbSession, _user: CurrentUser) -> ZoneResponse:
    """Return details of a specific zone."""
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise NotFoundError("Zone", str(zone_id))
    return ZoneResponse.model_validate(zone)


@router.put("/zones/{zone_id}", response_model=ZoneResponse, summary="Update zone")
async def update_zone(
    zone_id: UUID, db: DbSession, payload: ZoneUpdate, _user: CurrentUser
) -> ZoneResponse:
    """Update zone details."""
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise NotFoundError("Zone", str(zone_id))
        
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(zone, field, val)
        
    await db.flush()
    await db.refresh(zone)
    return ZoneResponse.model_validate(zone)


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete zone")
async def delete_zone(zone_id: UUID, db: DbSession, _user: CurrentUser) -> None:
    """Delete a zone."""
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise NotFoundError("Zone", str(zone_id))
    await db.delete(zone)
    await db.flush()
