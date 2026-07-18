"""Recommendation API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, HTTPException

from app.api.deps import CurrentUser, DbSession, ManagerOrAdmin
from app.models.recommendation import RecommendationStatus
from app.schemas.common import PaginatedResponse
from app.schemas.recommendation import RecommendationResponse, RecommendationStatusUpdate
from app.services.recommendation_service import RecommendationService
from app.services.recommendations import (
    generate_recommendations,
    approve_recommendation,
    reject_recommendation,
)

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[RecommendationResponse],
    summary="List recommendations",
)
async def list_recommendations(
    db: DbSession,
    _user: CurrentUser,
    status: RecommendationStatus | None = Query(default=None),
    startup_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedResponse[RecommendationResponse]:
    """Return paginated AI-generated seat optimization recommendations."""
    return await RecommendationService(db).list_recommendations(
        status=status,
        startup_id=startup_id,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/scan",
    response_model=list[RecommendationResponse],
    summary="Scan and generate recommendations",
)
async def scan_recommendations(
    db: DbSession,
    _user: ManagerOrAdmin,
    cushion: int = Query(default=2, ge=0),
) -> list[RecommendationResponse]:
    """Scan and generate seat reallocation optimization recommendations."""
    recs = await generate_recommendations(db, cushion=cushion)
    return [RecommendationService._to_response(r) for r in recs]


@router.get(
    "/{recommendation_id}",
    response_model=RecommendationResponse,
    summary="Get recommendation",
)
async def get_recommendation(
    recommendation_id: UUID,
    db: DbSession,
    _user: CurrentUser,
) -> RecommendationResponse:
    """Return a single recommendation by ID."""
    return await RecommendationService(db).get_recommendation(recommendation_id)


@router.post(
    "/{recommendation_id}/approve",
    response_model=RecommendationResponse,
    summary="Approve recommendation",
)
async def approve_rec(
    recommendation_id: UUID,
    db: DbSession,
    user: ManagerOrAdmin,
) -> RecommendationResponse:
    """Approve a recommendation, updating seat allocations accordingly."""
    try:
        rec = await approve_recommendation(db, recommendation_id, user.id)
        return RecommendationService._to_response(rec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{recommendation_id}/reject",
    response_model=RecommendationResponse,
    summary="Reject recommendation",
)
async def reject_rec(
    recommendation_id: UUID,
    db: DbSession,
    user: ManagerOrAdmin,
) -> RecommendationResponse:
    """Reject a recommendation."""
    try:
        rec = await reject_recommendation(db, recommendation_id, user.id)
        return RecommendationService._to_response(rec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch(
    "/{recommendation_id}/status",
    response_model=RecommendationResponse,
    summary="Update recommendation status",
)
async def update_recommendation_status(
    recommendation_id: UUID,
    db: DbSession,
    user: ManagerOrAdmin,
    payload: RecommendationStatusUpdate,
) -> RecommendationResponse:
    """Accept, reject, or mark a recommendation as implemented."""
    # If the payload indicates ACCEPTED or REJECTED, we delegate to our business logic to update DB and allocations.
    if payload.status == RecommendationStatus.ACCEPTED:
        try:
            rec = await approve_recommendation(db, recommendation_id, user.id)
            return RecommendationService._to_response(rec)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    elif payload.status == RecommendationStatus.REJECTED:
        try:
            rec = await reject_recommendation(db, recommendation_id, user.id)
            return RecommendationService._to_response(rec)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        return await RecommendationService(db).update_status(
            recommendation_id,
            payload,
            resolved_by=user.id,
        )
