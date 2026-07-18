"""Recommendation lifecycle business logic."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.exceptions import NotFoundError
from app.models.recommendation import RecommendationStatus
from app.repositories.recommendation_repository import RecommendationRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.recommendation import RecommendationResponse, RecommendationStatusUpdate


class RecommendationService:
    """Fetch and resolve seat optimization recommendations."""

    def __init__(self, session: AsyncSession) -> None:
        self._recommendations = RecommendationRepository(session)

    async def list_recommendations(
        self,
        *,
        status: RecommendationStatus | None = None,
        startup_id: UUID | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResponse[RecommendationResponse]:
        offset = (page - 1) * page_size
        items, total = await self._recommendations.list(
            status=status,
            startup_id=startup_id,
            limit=page_size,
            offset=offset,
        )
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return PaginatedResponse(
            items=[self._to_response(r) for r in items],
            meta=PaginationMeta(
                page=page,
                page_size=page_size,
                total_items=total,
                total_pages=total_pages,
            ),
        )

    async def get_recommendation(self, recommendation_id: UUID) -> RecommendationResponse:
        rec = await self._recommendations.get_by_id(recommendation_id)
        if not rec:
            raise NotFoundError("Recommendation", str(recommendation_id))
        return self._to_response(rec)

    async def update_status(
        self,
        recommendation_id: UUID,
        payload: RecommendationStatusUpdate,
        *,
        resolved_by: UUID,
    ) -> RecommendationResponse:
        rec = await self._recommendations.get_by_id(recommendation_id)
        if not rec:
            raise NotFoundError("Recommendation", str(recommendation_id))

        rec.status = payload.status
        rec.resolved_by = resolved_by
        rec.resolved_at = datetime.now(timezone.utc)
        updated = await self._recommendations.update(rec)
        return self._to_response(updated)

    @staticmethod
    def _to_response(rec) -> RecommendationResponse:
        return RecommendationResponse(
            id=str(rec.id),
            startup_id=str(rec.startup_id) if rec.startup_id else None,
            startup_name=rec.startup.name if rec.startup else None,
            recommendation_type=rec.recommendation_type,
            title=rec.title,
            description=rec.description,
            priority=rec.priority,
            status=rec.status,
            impact_seats=rec.impact_seats,
            impact_revenue=rec.impact_revenue,
            data=rec.data,
            resolved_at=rec.resolved_at,
            created_at=rec.created_at,
            updated_at=rec.updated_at,
        )
