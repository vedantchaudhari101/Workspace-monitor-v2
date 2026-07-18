"""Recommendation engine response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.models.recommendation import (
    RecommendationPriority,
    RecommendationStatus,
    RecommendationType,
)
from app.schemas.common import ORMModel


class RecommendationResponse(ORMModel):
    id: str
    startup_id: str | None
    startup_name: str | None = None
    recommendation_type: RecommendationType
    title: str
    description: str
    priority: RecommendationPriority
    status: RecommendationStatus
    impact_seats: int | None
    impact_revenue: float | None
    data: dict | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RecommendationStatusUpdate(ORMModel):
    status: RecommendationStatus = Field(
        description="New status: ACCEPTED, REJECTED, or IMPLEMENTED"
    )
