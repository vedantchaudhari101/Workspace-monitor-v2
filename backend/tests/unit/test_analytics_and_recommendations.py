"""Unit tests for occupancy snapshots, forecasting, and recommendations services."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.models.occupancy_snapshot import PeriodType, OccupancySnapshot
from app.models.recommendation import Recommendation, RecommendationType, RecommendationStatus
from app.models.startup import Startup
from app.models.seat_allocation import SeatAllocation
from app.services.analytics import create_occupancy_snapshot
from app.services.recommendations import generate_recommendations, approve_recommendation, reject_recommendation


@pytest.mark.asyncio
async def test_create_occupancy_snapshot():
    """Test creating occupancy snapshot for building and startups."""
    mock_db = AsyncMock()
    building_id = uuid.uuid4()
    startup_id = uuid.uuid4()

    # Create mock seats, events, allocations
    mock_seat = MagicMock()
    mock_seat.id = uuid.uuid4()
    
    mock_event = MagicMock()
    mock_event.seat_id = mock_seat.id
    mock_event.status = "OCCUPIED"

    mock_allocation = MagicMock()
    mock_allocation.seat_id = mock_seat.id
    mock_allocation.startup_id = startup_id
    mock_allocation.is_active = True

    # Setup database query execution results
    mock_db.execute = AsyncMock()
    
    # 1. seats_result
    mock_seats_result = MagicMock()
    mock_seats_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_seat])))
    
    # 2. events_result
    mock_events_result = MagicMock()
    mock_events_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_event])))
    
    # 3. allocations_result
    mock_allocations_result = MagicMock()
    mock_allocations_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_allocation])))

    mock_db.execute.side_effect = [
        mock_seats_result,
        mock_events_result,
        mock_allocations_result
    ]
    mock_db.commit = AsyncMock()

    snapshots = await create_occupancy_snapshot(mock_db, building_id, PeriodType.HOURLY)
    
    assert len(snapshots) == 2
    # Building snapshot
    assert snapshots[0].building_id == building_id
    assert snapshots[0].startup_id is None
    assert snapshots[0].total_seats == 1
    assert snapshots[0].occupied_seats == 1
    assert snapshots[0].occupancy_rate == 100.0
    
    # Startup snapshot
    assert snapshots[1].building_id == building_id
    assert snapshots[1].startup_id == startup_id
    assert snapshots[1].total_seats == 1
    assert snapshots[1].occupied_seats == 1
    assert snapshots[1].occupancy_rate == 100.0


@pytest.mark.asyncio
async def test_generate_recommendations_reduction():
    """Test generating REDUCTION recommendations when occupancy is low."""
    mock_db = AsyncMock()
    startup_id = uuid.uuid4()
    building_id = uuid.uuid4()

    mock_startup = Startup(
        id=startup_id,
        name="Startup A",
        allocated_seats=5,
        monthly_rate_per_seat=100.0,
        is_active=True
    )

    # Mock query row for historical snapshots: (startup_id, building_id, avg_rate, avg_occupied, avg_allocated)
    mock_row = (startup_id, building_id, 40.0, 2.0, 5.0)
    mock_result = MagicMock()
    mock_result.all = MagicMock(return_value=[mock_row])
    
    mock_db.execute = AsyncMock()
    
    # 1. snapshots query result
    # 2. existing pending recommendations query result (none)
    mock_existing_result = MagicMock()
    mock_existing_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    
    # 3. active allocated count
    mock_count_result = MagicMock()
    mock_count_result.scalar_one = MagicMock(return_value=5)

    # snapshot metadata used to flag demo-derived recommendations
    mock_meta_result = MagicMock()
    mock_meta_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[{"demo": True}])))

    mock_db.execute.side_effect = [
        mock_result,
        mock_meta_result,
        mock_existing_result,
        mock_count_result
    ]
    
    mock_db.get = AsyncMock(side_effect=lambda model, pk: mock_startup if model == Startup else MagicMock(name="Building A"))
    mock_db.commit = AsyncMock()

    recs = await generate_recommendations(mock_db, cushion=1)
    
    assert len(recs) == 1
    assert recs[0].recommendation_type == RecommendationType.REDUCTION
    assert recs[0].impact_seats == -2  # unused (5 - 2 = 3) - cushion (1) = 2 seats to reduce
    assert recs[0].impact_revenue == 200.0
    assert recs[0].data["demo"] is True


@pytest.mark.asyncio
async def test_approve_recommendation_reduction():
    """Test approving REDUCTION recommendation."""
    mock_db = AsyncMock()
    rec_id = uuid.uuid4()
    startup_id = uuid.uuid4()
    building_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_rec = Recommendation(
        id=rec_id,
        startup_id=startup_id,
        recommendation_type=RecommendationType.REDUCTION,
        status=RecommendationStatus.PENDING,
        data={"building_id": str(building_id), "reduction_seats": 2},
        impact_seats=-2,
        impact_revenue=200.0
    )

    mock_startup = Startup(
        id=startup_id,
        name="Startup A",
        allocated_seats=5,
        monthly_rate_per_seat=100.0,
        is_active=True
    )

    mock_allocation = SeatAllocation(
        id=uuid.uuid4(),
        seat_id=uuid.uuid4(),
        startup_id=startup_id,
        is_active=True
    )

    mock_db.get = AsyncMock(side_effect=lambda model, pk: mock_rec if model == Recommendation else mock_startup)
    
    mock_allocs_res = MagicMock()
    mock_allocs_res.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_allocation])))
    mock_db.execute = AsyncMock(return_value=mock_allocs_res)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    resolved_rec = await approve_recommendation(mock_db, rec_id, user_id)
    
    assert resolved_rec.status == RecommendationStatus.ACCEPTED
    assert mock_startup.allocated_seats == 3
    assert not mock_allocation.is_active
    assert mock_allocation.deallocated_at is not None
