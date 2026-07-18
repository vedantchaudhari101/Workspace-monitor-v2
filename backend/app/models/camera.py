"""Camera model for CCTV camera configuration.

Stores camera stream URLs and configuration for the computer vision
occupancy detection pipeline. Each camera is associated with a
building and optionally linked to a specific floor and zone.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.building import Building


class Camera(UUIDMixin, TimestampMixin, Base):
    """CCTV camera used for occupancy monitoring.

    Stores the stream URL (RTSP/HTTP), resolution, and frame rate
    for each camera. Cameras belong to a building and can optionally
    be linked to a specific floor and zone to scope their detection
    area. The config JSON field stores flexible camera-specific
    settings such as detection thresholds or ROI polygons.
    """

    __tablename__ = "cameras"

    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buildings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    stream_url: Mapped[str] = mapped_column(String(500), nullable=False)
    floor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("floors.id", ondelete="SET NULL"),
        nullable=True,
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("zones.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    resolution_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    building: Mapped[Building] = relationship(
        "Building", back_populates="cameras", lazy="joined"
    )

    def __repr__(self) -> str:
        return (
            f"<Camera(id={self.id!r}, name={self.name!r}, "
            f"building_id={self.building_id!r}, is_active={self.is_active!r})>"
        )
