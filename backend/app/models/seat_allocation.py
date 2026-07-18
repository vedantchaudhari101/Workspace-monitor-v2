"""Seat allocation model tracking which seats are assigned to which startup.

Supports full reallocation history by tracking allocation and
deallocation timestamps. Active allocations have a null deallocated_at
and is_active set to True.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin
from app.models.seat import Seat
from app.models.startup import Startup


class SeatAllocation(UUIDMixin, TimestampMixin, Base):
    """Tracks seat-to-startup allocation with history.

    Each record represents a period during which a specific seat was
    allocated to a specific startup. When a seat is deallocated, the
    deallocated_at timestamp is set and is_active becomes False,
    preserving the full allocation history for analytics.
    """

    __tablename__ = "seat_allocations"
    __table_args__ = (
        Index("ix_seat_allocations_seat_active", "seat_id", "is_active"),
        Index("ix_seat_allocations_startup_active", "startup_id", "is_active"),
    )

    seat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("seats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    startup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("startups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    allocated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    deallocated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    seat: Mapped[Seat] = relationship(
        "Seat", back_populates="allocations", lazy="joined"
    )
    startup: Mapped[Startup] = relationship(
        "Startup", back_populates="seat_allocations", lazy="joined"
    )

    def __repr__(self) -> str:
        return (
            f"<SeatAllocation(id={self.id!r}, seat_id={self.seat_id!r}, "
            f"startup_id={self.startup_id!r}, is_active={self.is_active!r})>"
        )
