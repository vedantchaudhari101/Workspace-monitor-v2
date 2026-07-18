"""Recommendation model for AI-generated seat reallocation suggestions.

Stores AI-powered recommendations for optimizing workspace seat
allocations, including expansions, reductions, and reallocations.
Each recommendation has a priority, status lifecycle, and estimated
impact metrics.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.startup import Startup


class RecommendationType(str, enum.Enum):
    """Type classification for recommendations."""

    REALLOCATION = "REALLOCATION"
    EXPANSION = "EXPANSION"
    REDUCTION = "REDUCTION"
    OPTIMIZATION = "OPTIMIZATION"


class RecommendationPriority(str, enum.Enum):
    """Priority levels for recommendations."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecommendationStatus(str, enum.Enum):
    """Lifecycle status for recommendations."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    IMPLEMENTED = "IMPLEMENTED"


class Recommendation(UUIDMixin, TimestampMixin, Base):
    """AI-generated seat reallocation recommendation.

    Produced by the analytics engine based on occupancy trends,
    each recommendation suggests actions like reallocating
    underused seats, expanding a startup's allocation, or reducing
    over-provisioned space. Includes estimated impact on seat count
    and revenue, and follows a status lifecycle from PENDING through
    to IMPLEMENTED.
    """

    __tablename__ = "recommendations"

    startup_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("startups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recommendation_type: Mapped[RecommendationType] = mapped_column(
        nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[RecommendationPriority] = mapped_column(
        default=RecommendationPriority.MEDIUM, nullable=False
    )
    status: Mapped[RecommendationStatus] = mapped_column(
        default=RecommendationStatus.PENDING, nullable=False
    )
    impact_seats: Mapped[int | None] = mapped_column(Integer, nullable=True)
    impact_revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    startup: Mapped[Startup | None] = relationship(
        "Startup", back_populates="recommendations", lazy="joined"
    )

    def __repr__(self) -> str:
        return (
            f"<Recommendation(id={self.id!r}, type={self.recommendation_type!r}, "
            f"priority={self.priority!r}, status={self.status!r}, "
            f"startup_id={self.startup_id!r})>"
        )
