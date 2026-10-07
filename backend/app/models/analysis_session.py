"""Analysis session model — one row per processed video (or live run).

A session records what the CV pipeline did with a single input: which
camera it ran on, the source file, how far it got, real throughput metrics,
and the final summary computed from the occupancy transitions it observed.
Occupancy events produced during the run reference the session through
``occupancy_events.session_id``.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class SessionStatus(str, enum.Enum):
    """Lifecycle of an analysis session."""

    UPLOADED = "UPLOADED"
    CALIBRATING = "CALIBRATING"
    TRACKING = "TRACKING"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class AnalysisSession(UUIDMixin, TimestampMixin, Base):
    """A single run of the occupancy pipeline over one video source."""

    __tablename__ = "analysis_sessions"

    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mode: Mapped[str] = mapped_column(String(16), default="video", nullable=False)
    pipeline: Mapped[str] = mapped_column(String(16), default="report", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=SessionStatus.UPLOADED.value, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    video_fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_frames: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frame_h: Mapped[int | None] = mapped_column(Integer, nullable=True)

    frames_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    frames_inferred: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_inference_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    seat_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AnalysisSession(id={self.id!r}, status={self.status!r}, file={self.source_filename!r})>"
