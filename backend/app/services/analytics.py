"""Analytics snapshot and aggregation services."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID
from collections import defaultdict

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.seat import Seat
from app.models.zone import Zone
from app.models.floor import Floor
from app.models.seat_allocation import SeatAllocation
from app.models.occupancy_event import OccupancyEvent, OccupancyStatus
from app.models.occupancy_snapshot import OccupancySnapshot, PeriodType

logger = logging.getLogger(__name__)

async def create_occupancy_snapshot(
    db: AsyncSession,
    building_id: UUID,
    period_type: PeriodType = PeriodType.HOURLY,
) -> list[OccupancySnapshot]:
    """Create periodic occupancy snapshots for a building and its active startups."""
    now = datetime.now(timezone.utc)
    snapshots = []

    # 1. Get all active seats in the building
    seats_query = (
        select(Seat)
        .join(Zone, Zone.id == Seat.zone_id)
        .join(Floor, Floor.id == Zone.floor_id)
        .where(Floor.building_id == building_id, Seat.is_active.is_(True))
    )
    seats_result = await db.execute(seats_query)
    seats = list(seats_result.scalars().all())
    seat_ids = [s.id for s in seats]

    if not seat_ids:
        logger.warning(f"No active seats found in building {building_id}")
        return []

    # 2. Get the latest occupancy event for each seat
    latest_subq = (
        select(
            OccupancyEvent.seat_id,
            func.max(OccupancyEvent.detected_at).label("max_detected_at"),
        )
        .where(OccupancyEvent.seat_id.in_(seat_ids))
        .group_by(OccupancyEvent.seat_id)
        .subquery()
    )

    events_query = (
        select(OccupancyEvent)
        .join(
            latest_subq,
            and_(
                OccupancyEvent.seat_id == latest_subq.c.seat_id,
                OccupancyEvent.detected_at == latest_subq.c.max_detected_at,
            ),
        )
    )
    events_result = await db.execute(events_query)
    events = list(events_result.scalars().all())
    event_map = {e.seat_id: e for e in events}

    # 3. Get all active seat allocations in the building
    allocations_query = (
        select(SeatAllocation)
        .where(
            SeatAllocation.seat_id.in_(seat_ids),
            SeatAllocation.is_active.is_(True),
        )
    )
    allocations_result = await db.execute(allocations_query)
    allocations = list(allocations_result.scalars().all())
    alloc_map = {a.seat_id: a for a in allocations}

    # Calculate building-wide stats
    b_total = len(seats)
    b_occupied = sum(
        1 for s in seats
        if s.id in event_map and event_map[s.id].status == OccupancyStatus.OCCUPIED
    )
    b_rate = (b_occupied / b_total * 100.0) if b_total > 0 else 0.0

    building_snapshot = OccupancySnapshot(
        building_id=building_id,
        floor_id=None,
        startup_id=None,
        snapshot_time=now,
        total_seats=b_total,
        occupied_seats=b_occupied,
        occupancy_rate=round(b_rate, 2),
        period_type=period_type,
        metadata_={},
    )
    db.add(building_snapshot)
    snapshots.append(building_snapshot)

    # Compute per-startup occupancy rates
    startup_allocations = defaultdict(list)
    for a in allocations:
        startup_allocations[a.startup_id].append(a)

    for startup_id, s_allocs in startup_allocations.items():
        s_total = len(s_allocs)
        s_occupied = sum(
            1 for a in s_allocs
            if a.seat_id in event_map and event_map[a.seat_id].status == OccupancyStatus.OCCUPIED
        )
        s_rate = (s_occupied / s_total * 100.0) if s_total > 0 else 0.0

        startup_snapshot = OccupancySnapshot(
            building_id=building_id,
            floor_id=None,
            startup_id=startup_id,
            snapshot_time=now,
            total_seats=s_total,
            occupied_seats=s_occupied,
            occupancy_rate=round(s_rate, 2),
            period_type=period_type,
            metadata_={},
        )
        db.add(startup_snapshot)
        snapshots.append(startup_snapshot)

    await db.commit()
    return snapshots
