"""Seat model representing individual seats within a zone.

Seats are the lowest level in the spatial hierarchy
(Building -> Floor -> Zone -> Seat). Each seat has optional
coordinate and bounding box data for computer-vision mapping
in camera frames.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.occupancy_event import OccupancyEvent
    from app.models.seat_allocation import SeatAllocation
    from app.models.zone import Zone


class Seat(UUIDMixin, TimestampMixin, Base):
    """Individual seat within a workspace zone.

    Tracks physical seat positions with optional pixel coordinates
    (x, y) and bounding box dimensions (width, height) for mapping
    to camera frames used by the computer vision occupancy detection
    pipeline. Each seat has a unique label within its zone.
    """

    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("zone_id", "seat_label", name="uq_seats_zone_label"),
    )

    zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("zones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seat_label: Mapped[str] = mapped_column(String(50), nullable=False)
    x_coordinate: Mapped[float | None] = mapped_column(Float, nullable=True)
    y_coordinate: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[float | None] = mapped_column(Float, nullable=True)
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # DETECTED = created by the CV calibration engine, SEED = demo data,
    # MANUAL = created through the API.
    source: Mapped[str] = mapped_column(String(16), default="MANUAL", nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    zone: Mapped[Zone] = relationship(
        "Zone", back_populates="seats", lazy="joined"
    )
    allocations: Mapped[list[SeatAllocation]] = relationship(
        "SeatAllocation", back_populates="seat", lazy="selectin",
        cascade="all, delete-orphan",
    )
    occupancy_events: Mapped[list[OccupancyEvent]] = relationship(
        "OccupancyEvent", back_populates="seat", lazy="noload",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Seat(id={self.id!r}, label={self.seat_label!r}, "
            f"zone_id={self.zone_id!r})>"
        )
