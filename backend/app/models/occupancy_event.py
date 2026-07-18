"""Occupancy event model for real-time CV detection results.

This is the HOTTEST table in the system — expected to accumulate
millions of rows as the computer vision pipeline continuously
detects seat occupancy status from camera frames. Heavily indexed
for time-range and latest-status queries.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin
from app.models.camera import Camera
from app.models.seat import Seat


class OccupancyStatus(str, enum.Enum):
    """Detected occupancy status for a seat."""

    OCCUPIED = "OCCUPIED"
    VACANT = "VACANT"
    UNKNOWN = "UNKNOWN"


class OccupancyEvent(UUIDMixin, TimestampMixin, Base):
    """Real-time occupancy detection event from computer vision.

    Records individual detections from the CV pipeline, including
    which seat was observed, the detection status (occupied/vacant),
    the confidence score, and the timestamp. The person_bbox field
    stores the bounding box coordinates of the detected person
    in the camera frame as {x, y, w, h}.

    This table is the highest-volume table in the system and is
    optimized with multiple indexes for time-series queries.
    """

    __tablename__ = "occupancy_events"
    __table_args__ = (
        Index(
            "ix_occupancy_events_seat_detected",
            "seat_id",
            "detected_at",
            postgresql_using="btree",
        ),
        Index(
            "ix_occupancy_events_camera_detected",
            "camera_id",
            "detected_at",
            postgresql_using="btree",
        ),
        Index(
            "ix_occupancy_events_detected_at",
            "detected_at",
            postgresql_using="btree",
        ),
    )

    seat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("seats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[OccupancyStatus] = mapped_column(nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    person_bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    seat: Mapped[Seat] = relationship(
        "Seat", back_populates="occupancy_events", lazy="joined"
    )
    camera: Mapped[Camera] = relationship("Camera", lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<OccupancyEvent(id={self.id!r}, seat_id={self.seat_id!r}, "
            f"status={self.status!r}, confidence={self.confidence!r}, "
            f"detected_at={self.detected_at!r})>"
        )
