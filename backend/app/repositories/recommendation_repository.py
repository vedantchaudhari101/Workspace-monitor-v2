"""Recommendation data access layer."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.recommendation import Recommendation, RecommendationStatus


class RecommendationRepository:
    """CRUD operations for AI-generated recommendations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(
        self,
        *,
        status: RecommendationStatus | None = None,
        startup_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Recommendation], int]:
        query = select(Recommendation).options(joinedload(Recommendation.startup))
        count_query = select(func.count()).select_from(Recommendation)

        filters = []
        if status:
            filters.append(Recommendation.status == status)
        if startup_id:
            filters.append(Recommendation.startup_id == startup_id)

        if filters:
            from sqlalchemy import and_

            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))

        total = int((await self._session.execute(count_query)).scalar_one())
        result = await self._session.execute(
            query.order_by(Recommendation.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().unique().all()), total

    async def get_by_id(self, recommendation_id: UUID) -> Recommendation | None:
        result = await self._session.execute(
            select(Recommendation)
            .options(joinedload(Recommendation.startup))
            .where(Recommendation.id == recommendation_id)
        )
        return result.scalar_one_or_none()

    async def update(self, recommendation: Recommendation) -> Recommendation:
        await self._session.flush()
        await self._session.refresh(recommendation)
        return recommendation
