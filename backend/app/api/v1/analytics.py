"""Analytics and forecasting API routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func, and_

from app.api.deps import CurrentUser, DbSession
from app.config import get_settings
from app.models.occupancy_snapshot import OccupancySnapshot, PeriodType
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.analytics import ForecastItem, OccupancySnapshotResponse
from app.analytics.forecaster import predict_occupancy_trend
from app.services.insights import build_insights
from app.services.seat_history import compute_analytics, recent_activity, seat_history

router = APIRouter()


@router.get(
    "/forecast",
    response_model=list[ForecastItem],
    summary="Predict occupancy trend",
)
async def forecast_occupancy(
    db: DbSession,
    _user: CurrentUser,
    building_id: UUID = Query(..., description="Building ID to forecast"),
    days_ahead: int = Query(default=7, ge=1, le=30, description="Number of days to predict"),
) -> list[ForecastItem]:
    """Return hourly predicted occupancy metrics for the next N days."""
    predictions = await predict_occupancy_trend(db, building_id, days_ahead)
    return [ForecastItem(**p) for p in predictions]


@router.get(
    "/snapshots",
    response_model=PaginatedResponse[OccupancySnapshotResponse],
    summary="Get historical occupancy snapshots",
)
async def list_snapshots(
    db: DbSession,
    _user: CurrentUser,
    building_id: UUID = Query(..., description="Building ID to query"),
    floor_id: UUID | None = Query(default=None, description="Optional Floor ID filter"),
    startup_id: UUID | None = Query(default=None, description="Optional Startup ID filter"),
    period_type: PeriodType | None = Query(default=None, description="Optional Period Type filter (HOURLY, MINUTE_5, etc.)"),
    since: datetime | None = Query(default=None, description="Start date filter"),
    until: datetime | None = Query(default=None, description="End date filter"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedResponse[OccupancySnapshotResponse]:
    """Return paginated historical occupancy snapshots based on search filters."""
    query = select(OccupancySnapshot)
    count_query = select(func.count()).select_from(OccupancySnapshot)

    filters = [OccupancySnapshot.building_id == building_id]

    if floor_id:
        filters.append(OccupancySnapshot.floor_id == floor_id)
    if startup_id:
        filters.append(OccupancySnapshot.startup_id == startup_id)
    if period_type:
        filters.append(OccupancySnapshot.period_type == period_type)
    if since:
        filters.append(OccupancySnapshot.snapshot_time >= since)
    if until:
        filters.append(OccupancySnapshot.snapshot_time <= until)

    query = query.where(and_(*filters)).order_by(OccupancySnapshot.snapshot_time.desc())
    count_query = count_query.where(and_(*filters))

    total = int((await db.execute(count_query)).scalar_one())
    offset = (page - 1) * page_size

    result = await db.execute(query.limit(page_size).offset(offset))
    snapshots = list(result.scalars().all())

    total_pages = (total + page_size - 1) // page_size if page_size else 0

    return PaginatedResponse(
        items=[
            OccupancySnapshotResponse(
                id=str(s.id),
                building_id=str(s.building_id),
                floor_id=str(s.floor_id) if s.floor_id else None,
                startup_id=str(s.startup_id) if s.startup_id else None,
                snapshot_time=s.snapshot_time,
                total_seats=s.total_seats,
                occupied_seats=s.occupied_seats,
                occupancy_rate=s.occupancy_rate,
                period_type=s.period_type,
                metadata=s.metadata_ or {},
            )
            for s in snapshots
        ],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=total_pages,
        ),
    )


def _demo(include_demo: bool | None) -> bool:
    return get_settings().DEMO_MODE if include_demo is None else include_demo


@router.get(
    "/comprehensive/{building_id}",
    summary="Get comprehensive occupancy analytics",
)
async def get_comprehensive_analytics(
    db: DbSession,
    _user: CurrentUser,
    building_id: UUID,
    range_hours: float = Query(default=24, gt=0, le=168, description="Number of hours to analyze"),
    include_demo: bool | None = Query(default=None, description="Include seeded/simulated data (defaults to DEMO_MODE)"),
    tz_offset_minutes: int = Query(default=0, ge=-840, le=840, description="Viewer UTC offset for hour-of-day charts"),
):
    """Time-weighted seat and building analytics.

    Durations, utilization and sessions are measured from occupancy state
    changes, scoped to the building and range. The original response keys are
    preserved; new keys (hourly, heatmap, capacity, startup_stats, sources,
    window) are added.
    """
    return await compute_analytics(db, building_id, range_hours, _demo(include_demo), tz_offset_minutes)


@router.get("/heatmap/{building_id}", summary="Seat × hour-of-day utilization")
async def get_heatmap(
    db: DbSession,
    _user: CurrentUser,
    building_id: UUID,
    range_hours: float = Query(default=168, gt=0, le=168),
    include_demo: bool | None = Query(default=None),
    tz_offset_minutes: int = Query(default=0, ge=-840, le=840),
):
    data = await compute_analytics(db, building_id, range_hours, _demo(include_demo), tz_offset_minutes)
    return {"window": data["window"], "sources": data["sources"], **data["heatmap"]}


@router.get("/seats/{seat_id}/history", summary="Seat occupancy history")
async def get_seat_history(
    db: DbSession,
    _user: CurrentUser,
    seat_id: UUID,
    range_hours: float = Query(default=24, gt=0, le=168),
    include_demo: bool | None = Query(default=None),
):
    """Measured stats, state intervals and raw events for one seat."""
    data = await seat_history(db, seat_id, range_hours, _demo(include_demo))
    if data is None:
        raise HTTPException(status_code=404, detail="Seat not found.")
    return data


@router.get("/activity/{building_id}", summary="Recent seat changes")
async def get_activity(
    db: DbSession,
    _user: CurrentUser,
    building_id: UUID,
    limit: int = Query(default=30, ge=1, le=200),
    range_hours: float = Query(default=24, gt=0, le=168),
    include_demo: bool | None = Query(default=None),
):
    return await recent_activity(db, building_id, limit, _demo(include_demo), range_hours)


@router.get("/insights/{building_id}", summary="Workspace health, measured insights and rule-based recommendations")
async def get_insights(
    db: DbSession,
    _user: CurrentUser,
    building_id: UUID,
    range_hours: float = Query(default=168, gt=0, le=168),
    include_demo: bool | None = Query(default=None),
    tz_offset_minutes: int = Query(default=0, ge=-840, le=840),
):
    data = await compute_analytics(db, building_id, range_hours, _demo(include_demo), tz_offset_minutes)
    return build_insights(data)
