"""Floor model representing floors within a building.

Floors are the second level in the spatial hierarchy
(Building -> Floor -> Zone -> Seat) and contain multiple zones
that logically group seats together.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.building import Building
    from app.models.zone import Zone


class Floor(UUIDMixin, TimestampMixin, Base):
    """Floor within a building.

    Each floor belongs to exactly one building and contains one or
    more zones. The floor_number provides the physical ordering,
    while the name gives a human-readable label.
    """

    __tablename__ = "floors"

    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buildings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    floor_number: Mapped[int] = mapped_column(Integer, nullable=False)
    total_capacity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    building: Mapped[Building] = relationship(
        "Building", back_populates="floors", lazy="joined"
    )
    zones: Mapped[list[Zone]] = relationship(
        "Zone", back_populates="floor", lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Floor(id={self.id!r}, name={self.name!r}, "
            f"floor_number={self.floor_number!r}, "
            f"building_id={self.building_id!r})>"
        )
