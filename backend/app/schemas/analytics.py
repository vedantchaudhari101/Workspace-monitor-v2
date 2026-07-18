"""Schemas for analytics snapshots and predictions."""

from __future__ import annotations

from datetime import datetime
from pydantic import Field

from app.models.occupancy_snapshot import PeriodType
from app.schemas.common import ORMModel


class ForecastItem(ORMModel):
    """Hourly predicted occupancy data."""

    timestamp: datetime
    predicted_occupancy_rate: float = Field(description="Percentage 0-100")
    predicted_occupied_seats: int
    total_seats: int


class OccupancySnapshotResponse(ORMModel):
    """Historical occupancy snapshot record."""

    id: str
    building_id: str
    floor_id: str | None = None
    startup_id: str | None = None
    snapshot_time: datetime
    total_seats: int
    occupied_seats: int
    occupancy_rate: float = Field(description="Percentage 0-100")
    period_type: PeriodType
    metadata_: dict | None = Field(default=None, alias="metadata")
