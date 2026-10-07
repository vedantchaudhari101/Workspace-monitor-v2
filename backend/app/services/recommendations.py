"""Recommendation aggregation and scanner services."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy import select, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.startup import Startup
from app.models.seat import Seat
from app.models.zone import Zone
from app.models.floor import Floor
from app.models.seat_allocation import SeatAllocation
from app.models.occupancy_snapshot import OccupancySnapshot
from app.models.recommendation import (
    Recommendation,
    RecommendationType,
    RecommendationPriority,
    RecommendationStatus,
)

logger = logging.getLogger(__name__)

async def generate_recommendations(db: AsyncSession, cushion: int = 2, expansion_count: int = 2) -> list[Recommendation]:
    """Scan startups and generate seat allocation optimization recommendations."""
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    # 1. Fetch startups and their average occupancy rates over the last 7 days grouped by building
    # We query snapshots where startup_id is not null
    query = (
        select(
            OccupancySnapshot.startup_id,
            OccupancySnapshot.building_id,
            func.avg(OccupancySnapshot.occupancy_rate).label("avg_rate"),
            func.avg(OccupancySnapshot.occupied_seats).label("avg_occupied"),
            func.avg(OccupancySnapshot.total_seats).label("avg_allocated")
        )
        .where(
            OccupancySnapshot.startup_id.isnot(None),
            OccupancySnapshot.snapshot_time >= seven_days_ago
        )
        .group_by(OccupancySnapshot.startup_id, OccupancySnapshot.building_id)
    )
    result = await db.execute(query)
    rows = result.all()

    # Snapshots are only produced by the seed script today (no snapshot job
    # runs on live data), so mark recommendations derived from demo snapshots.
    meta_rows = await db.execute(
        select(OccupancySnapshot.metadata_).where(
            OccupancySnapshot.startup_id.isnot(None),
            OccupancySnapshot.snapshot_time >= seven_days_ago,
        )
    )
    demo_basis = any(isinstance(m, dict) and m.get("demo") for m in meta_rows.scalars().all())

    recommendations = []

    for startup_id, building_id, avg_rate, avg_occupied, avg_allocated in rows:
        if avg_rate is None:
            continue

        # Fetch Startup model
        startup = await db.get(Startup, startup_id)
        if not startup or not startup.is_active:
            continue

        # Get building name
        from app.models.building import Building
        building = await db.get(Building, building_id)
        building_name = building.name if building else "Building"

        # Check for existing pending recommendation of the same type for this startup and building
        # to avoid duplicates
        existing_query = select(Recommendation).where(
            Recommendation.startup_id == startup_id,
            Recommendation.status == RecommendationStatus.PENDING,
            Recommendation.data["building_id"].as_string() == str(building_id)
        )
        existing_result = await db.execute(existing_query)
        existing_recs = existing_result.scalars().all()
        existing_types = {r.recommendation_type for r in existing_recs}

        # Rule 1 (Reduction): avg occupancy < 60%
        if avg_rate < 60.0:
            if RecommendationType.REDUCTION not in existing_types:
                # Count current active seat allocations for this startup in this building
                allocated_query = (
                    select(func.count(SeatAllocation.id))
                    .join(Seat, Seat.id == SeatAllocation.seat_id)
                    .join(Zone, Zone.id == Seat.zone_id)
                    .join(Floor, Floor.id == Zone.floor_id)
                    .where(
                        Floor.building_id == building_id,
                        SeatAllocation.startup_id == startup_id,
                        SeatAllocation.is_active.is_(True)
                    )
                )
                allocated_in_building = (await db.execute(allocated_query)).scalar_one() or 0

                unused_seats = allocated_in_building - avg_occupied
                X = int(unused_seats - cushion)

                if X > 0:
                    impact_revenue = X * startup.monthly_rate_per_seat
                    rec = Recommendation(
                        startup_id=startup_id,
                        recommendation_type=RecommendationType.REDUCTION,
                        title=f"Reduce seat allocation for {startup.name} in {building_name}",
                        description=(
                            f"Average occupancy for {startup.name} over the last 7 days was {round(avg_rate, 1)}%. "
                            f"Suggest reducing allocation by {X} seats (current: {allocated_in_building}, avg occupied: {round(avg_occupied, 1)})."
                        ),
                        priority=RecommendationPriority.MEDIUM if avg_rate > 30 else RecommendationPriority.HIGH,
                        status=RecommendationStatus.PENDING,
                        impact_seats=-X,
                        impact_revenue=round(impact_revenue, 2),
                        data={
                            "building_id": str(building_id),
                            "reduction_seats": X,
                            "basis": "occupancy_snapshots_7d",
                            "demo": demo_basis,
                        }
                    )
                    db.add(rec)
                    recommendations.append(rec)

        # Rule 2 (Expansion): avg occupancy > 90%
        elif avg_rate > 90.0:
            if RecommendationType.EXPANSION not in existing_types:
                # Find all seats in the building
                all_seats_query = (
                    select(Seat.id)
                    .join(Zone, Zone.id == Seat.zone_id)
                    .join(Floor, Floor.id == Zone.floor_id)
                    .where(Floor.building_id == building_id, Seat.is_active.is_(True))
                )
                all_seats_res = await db.execute(all_seats_query)
                building_seat_ids = [s_id for s_id in all_seats_res.scalars().all()]

                if building_seat_ids:
                    # Find allocated seats in this building
                    allocated_seats_query = (
                        select(SeatAllocation.seat_id)
                        .where(
                            SeatAllocation.seat_id.in_(building_seat_ids),
                            SeatAllocation.is_active.is_(True)
                        )
                    )
                    allocated_seats_res = await db.execute(allocated_seats_query)
                    allocated_seat_ids = set(allocated_seats_res.scalars().all())

                    vacant_unallocated_seat_ids = [s_id for s_id in building_seat_ids if s_id not in allocated_seat_ids]
                    vacant_unallocated_count = len(vacant_unallocated_seat_ids)

                    if vacant_unallocated_count > 0:
                        Y = min(expansion_count, vacant_unallocated_count)
                        impact_revenue = Y * startup.monthly_rate_per_seat
                        rec = Recommendation(
                            startup_id=startup_id,
                            recommendation_type=RecommendationType.EXPANSION,
                            title=f"Expand seat allocation for {startup.name} in {building_name}",
                            description=(
                                f"Average occupancy for {startup.name} over the last 7 days was {round(avg_rate, 1)}%. "
                                f"Suggest expanding allocation by {Y} seats (vacant unallocated seats available: {vacant_unallocated_count})."
                            ),
                            priority=RecommendationPriority.MEDIUM,
                            status=RecommendationStatus.PENDING,
                            impact_seats=Y,
                            impact_revenue=round(impact_revenue, 2),
                            data={
                                "building_id": str(building_id),
                                "expansion_seats": Y,
                                "basis": "occupancy_snapshots_7d",
                                "demo": demo_basis,
                            }
                        )
                        db.add(rec)
                        recommendations.append(rec)

    await db.commit()
    return recommendations


async def approve_recommendation(db: AsyncSession, recommendation_id: UUID, resolved_by: UUID) -> Recommendation:
    """Approve a recommendation, updating startup and seat allocations."""
    rec = await db.get(Recommendation, recommendation_id)
    if not rec:
        raise ValueError(f"Recommendation {recommendation_id} not found")

    if rec.status != RecommendationStatus.PENDING:
        raise ValueError(f"Recommendation status is {rec.status}, must be PENDING")

    startup = await db.get(Startup, rec.startup_id)
    if not startup:
        raise ValueError(f"Startup {rec.startup_id} not found")

    building_id_str = rec.data.get("building_id") if rec.data else None
    if not building_id_str:
        raise ValueError("Building ID not found in recommendation data")
    building_id = UUID(building_id_str)

    if rec.recommendation_type == RecommendationType.REDUCTION:
        X = rec.data.get("reduction_seats", 0)
        
        # 1. Update startup allocation
        startup.allocated_seats = max(0, startup.allocated_seats - X)

        # 2. Soft-deallocate surplus seats in SeatAllocation
        # Fetch active allocations for this startup and building
        allocs_query = (
            select(SeatAllocation)
            .join(Seat, Seat.id == SeatAllocation.seat_id)
            .join(Zone, Zone.id == Seat.zone_id)
            .join(Floor, Floor.id == Zone.floor_id)
            .where(
                Floor.building_id == building_id,
                SeatAllocation.startup_id == rec.startup_id,
                SeatAllocation.is_active.is_(True)
            )
        )
        allocs_res = await db.execute(allocs_query)
        active_allocs = list(allocs_res.scalars().all())

        # Soft deallocate X seats
        for a in active_allocs[:X]:
            a.is_active = False
            a.deallocated_at = datetime.now(timezone.utc)

    elif rec.recommendation_type == RecommendationType.EXPANSION:
        Y = rec.data.get("expansion_seats", 0)

        # 1. Find Y vacant unallocated seats in the building
        all_seats_query = (
            select(Seat)
            .join(Zone, Zone.id == Seat.zone_id)
            .join(Floor, Floor.id == Zone.floor_id)
            .where(Floor.building_id == building_id, Seat.is_active.is_(True))
        )
        all_seats_res = await db.execute(all_seats_query)
        building_seats = list(all_seats_res.scalars().all())
        building_seat_ids = [s.id for s in building_seats]

        if building_seat_ids:
            # Find currently allocated seats in this building
            allocated_seats_query = (
                select(SeatAllocation.seat_id)
                .where(
                    SeatAllocation.seat_id.in_(building_seat_ids),
                    SeatAllocation.is_active.is_(True)
                )
            )
            allocated_seats_res = await db.execute(allocated_seats_query)
            allocated_seat_ids = set(allocated_seats_res.scalars().all())

            vacant_seats = [s for s in building_seats if s.id not in allocated_seat_ids]
            
            if len(vacant_seats) < Y:
                raise ValueError(f"Not enough vacant unallocated seats (needed {Y}, available {len(vacant_seats)})")

            # Update startup allocation
            startup.allocated_seats += Y

            # Create new allocations
            for s in vacant_seats[:Y]:
                new_alloc = SeatAllocation(
                    seat_id=s.id,
                    startup_id=rec.startup_id,
                    is_active=True,
                    allocated_at=datetime.now(timezone.utc)
                )
                db.add(new_alloc)
        else:
            raise ValueError("No active seats found in building")

    rec.status = RecommendationStatus.ACCEPTED
    rec.resolved_by = resolved_by
    rec.resolved_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(rec)
    return rec


async def reject_recommendation(db: AsyncSession, recommendation_id: UUID, resolved_by: UUID) -> Recommendation:
    """Reject a recommendation."""
    rec = await db.get(Recommendation, recommendation_id)
    if not rec:
        raise ValueError(f"Recommendation {recommendation_id} not found")

    if rec.status != RecommendationStatus.PENDING:
        raise ValueError(f"Recommendation status is {rec.status}, must be PENDING")

    rec.status = RecommendationStatus.REJECTED
    rec.resolved_by = resolved_by
    rec.resolved_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(rec)
    return rec
