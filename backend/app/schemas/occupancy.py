"""Occupancy detection and analytics schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.models.occupancy_event import OccupancyStatus
from app.schemas.common import ORMModel


class SeatLiveStatus(ORMModel):
    seat_id: str
    seat_label: str
    zone_id: str
    zone_name: str
    floor_id: str
    floor_name: str
    startup_id: str | None
    startup_name: str | None
    status: OccupancyStatus
    confidence: float | None
    detected_at: datetime | None


class OccupancyEventResponse(ORMModel):
    id: str
    seat_id: str
    camera_id: str
    status: OccupancyStatus
    confidence: float | None
    detected_at: datetime
    person_bbox: dict | None = None


class FloorOccupancySummary(ORMModel):
    floor_id: str
    floor_name: str
    total_seats: int
    occupied_seats: int
    vacant_seats: int
    occupancy_rate: float = Field(description="Percentage 0-100")


class LiveOccupancyResponse(ORMModel):
    building_id: str
    building_name: str
    timestamp: datetime
    total_seats: int
    occupied_seats: int
    vacant_seats: int
    unknown_seats: int
    occupancy_rate: float
    floors: list[FloorOccupancySummary] = Field(default_factory=list)
    seats: list[SeatLiveStatus] = Field(default_factory=list)
