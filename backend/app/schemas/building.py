"""Building and spatial hierarchy response schemas."""

from __future__ import annotations

from pydantic import Field, BaseModel
from uuid import UUID

from app.schemas.common import ORMModel
from app.models.zone import ZoneType


class FloorSummary(ORMModel):
    id: UUID | str
    name: str
    floor_number: int
    total_capacity: int
    is_active: bool


class BuildingSummary(ORMModel):
    id: UUID | str
    name: str
    address: str | None
    city: str | None
    total_capacity: int
    is_active: bool


class CameraSummary(ORMModel):
    id: UUID | str
    name: str
    stream_url: str
    floor_id: UUID | str | None = None
    zone_id: UUID | str | None = None
    is_active: bool


class BuildingDetail(BuildingSummary):
    floors: list[FloorSummary] = Field(default_factory=list)
    cameras: list[CameraSummary] = Field(default_factory=list)



class BuildingUtilization(ORMModel):
    building_id: UUID | str
    building_name: str
    total_seats: int
    occupied_seats: int
    vacant_seats: int
    occupancy_rate: float = Field(description="Percentage 0-100")
    allocated_seats: int
    utilization_vs_allocation: float = Field(
        description="Occupied seats as % of allocated contract seats"
    )


# --- CRUD schemas ---

class BuildingCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    total_capacity: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)


class BuildingUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    total_capacity: int | None = Field(default=None, ge=0)
    is_active: bool | None = Field(default=None)


class FloorCreate(BaseModel):
    building_id: UUID
    name: str = Field(min_length=1, max_length=100)
    floor_number: int
    total_capacity: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)


class FloorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    floor_number: int | None = Field(default=None)
    total_capacity: int | None = Field(default=None, ge=0)
    is_active: bool | None = Field(default=None)


class FloorResponse(ORMModel):
    id: UUID
    building_id: UUID
    name: str
    floor_number: int
    total_capacity: int
    is_active: bool


class ZoneCreate(BaseModel):
    floor_id: UUID
    name: str = Field(min_length=1, max_length=100)
    zone_type: ZoneType = Field(default=ZoneType.OPEN)
    total_capacity: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)


class ZoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    zone_type: ZoneType | None = Field(default=None)
    total_capacity: int | None = Field(default=None, ge=0)
    is_active: bool | None = Field(default=None)


class ZoneResponse(ORMModel):
    id: UUID
    floor_id: UUID
    name: str
    zone_type: ZoneType
    total_capacity: int
    is_active: bool
