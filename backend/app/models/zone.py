"""Zone model representing logical groupings of seats within a floor.

Zones are the third level in the spatial hierarchy
(Building -> Floor -> Zone -> Seat). Each zone has a type that
describes its purpose (open plan, private offices, meeting rooms, etc.).
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.floor import Floor
    from app.models.seat import Seat


class ZoneType(str, enum.Enum):
    """Type classification for workspace zones."""

    OPEN = "OPEN"
    PRIVATE = "PRIVATE"
    MEETING = "MEETING"
    COMMON = "COMMON"


class Zone(UUIDMixin, TimestampMixin, Base):
    """Logical zone within a floor.

    Zones group seats together by function or physical location.
    Each zone has a type (OPEN, PRIVATE, MEETING, COMMON) that
    describes its intended use. Zones belong to exactly one floor
    and contain one or more seats.
    """

    __tablename__ = "zones"

    floor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("floors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    zone_type: Mapped[ZoneType] = mapped_column(
        default=ZoneType.OPEN, nullable=False
    )
    total_capacity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    floor: Mapped[Floor] = relationship(
        "Floor", back_populates="zones", lazy="joined"
    )
    seats: Mapped[list[Seat]] = relationship(
        "Seat", back_populates="zone", lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Zone(id={self.id!r}, name={self.name!r}, "
            f"zone_type={self.zone_type!r}, floor_id={self.floor_id!r})>"
        )
