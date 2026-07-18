"""Occupancy snapshot model for periodic aggregated occupancy data.

Stores pre-computed occupancy statistics at configurable time
intervals (5-min, 15-min, hourly, daily, weekly, monthly) for
fast dashboard queries without scanning the raw events table.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class PeriodType(str, enum.Enum):
    """Aggregation period for occupancy snapshots."""

    MINUTE_5 = "MINUTE_5"
    MINUTE_15 = "MINUTE_15"
    HOURLY = "HOURLY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class OccupancySnapshot(UUIDMixin, TimestampMixin, Base):
    """Periodic aggregated occupancy snapshot.

    Pre-computed occupancy statistics aggregated at configurable
    time intervals. Can be scoped to a building, floor, or startup
    for flexible dashboard queries. The occupancy_rate is stored
    as a percentage (0-100) for direct display.
    """

    __tablename__ = "occupancy_snapshots"
    __table_args__ = (
        Index(
            "ix_occupancy_snapshots_building_time",
            "building_id",
            "snapshot_time",
        ),
        Index(
            "ix_occupancy_snapshots_startup_time",
            "startup_id",
            "snapshot_time",
        ),
    )

    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buildings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    floor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("floors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    startup_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("startups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    snapshot_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    total_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    occupied_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    occupancy_rate: Mapped[float] = mapped_column(Float, nullable=False)
    period_type: Mapped[PeriodType] = mapped_column(nullable=False)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<OccupancySnapshot(id={self.id!r}, "
            f"building_id={self.building_id!r}, "
            f"period={self.period_type!r}, "
            f"rate={self.occupancy_rate!r}%, "
            f"time={self.snapshot_time!r})>"
        )
