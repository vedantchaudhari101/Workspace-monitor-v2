"""Building model representing physical office buildings.

Each building contains multiple floors and may have cameras installed
for occupancy monitoring. Buildings are the top-level entity in the
spatial hierarchy: Building -> Floor -> Zone -> Seat.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.camera import Camera
    from app.models.floor import Floor


class Building(UUIDMixin, TimestampMixin, Base):
    """Physical building in the workspace platform.

    Represents an office building with a given capacity, containing
    floors and cameras. The metadata_ field stores flexible extra
    data such as operating hours, amenities, or contact information.
    """

    __tablename__ = "buildings"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_capacity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True
    )

    # Relationships
    floors: Mapped[list[Floor]] = relationship(
        "Floor", back_populates="building", lazy="selectin",
        cascade="all, delete-orphan",
    )
    cameras: Mapped[list[Camera]] = relationship(
        "Camera", back_populates="building", lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Building(id={self.id!r}, name={self.name!r}, "
            f"city={self.city!r}, capacity={self.total_capacity!r})>"
        )
