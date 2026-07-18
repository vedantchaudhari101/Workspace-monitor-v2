"""Occupancy event and live status data access layer."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.floor import Floor
from app.models.occupancy_event import OccupancyEvent, OccupancyStatus
from app.models.seat import Seat
from app.models.seat_allocation import SeatAllocation
from app.models.startup import Startup
from app.models.zone import Zone


class OccupancyRepository:
    """Queries for live occupancy and historical events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_latest_events_for_building(self, building_id: UUID) -> list[OccupancyEvent]:
        """Return the most recent event per seat for a building."""
        latest_subq = (
            select(
                OccupancyEvent.seat_id,
                func.max(OccupancyEvent.detected_at).label("max_detected_at"),
            )
            .join(Seat, Seat.id == OccupancyEvent.seat_id)
            .join(Zone, Zone.id == Seat.zone_id)
            .join(Floor, Floor.id == Zone.floor_id)
            .where(Floor.building_id == building_id, Seat.is_active.is_(True))
            .group_by(OccupancyEvent.seat_id)
            .subquery()
        )

        query = (
            select(OccupancyEvent)
            .join(
                latest_subq,
                and_(
                    OccupancyEvent.seat_id == latest_subq.c.seat_id,
                    OccupancyEvent.detected_at == latest_subq.c.max_detected_at,
                ),
            )
            .options(
                joinedload(OccupancyEvent.seat)
                .joinedload(Seat.zone)
                .joinedload(Zone.floor),
            )
        )
        result = await self._session.execute(query)
        return list(result.scalars().unique().all())

    async def list_seats_for_building(self, building_id: UUID) -> list[Seat]:
        query = (
            select(Seat)
            .join(Zone, Zone.id == Seat.zone_id)
            .join(Floor, Floor.id == Zone.floor_id)
            .where(Floor.building_id == building_id, Seat.is_active.is_(True))
            .options(
                joinedload(Seat.zone).joinedload(Zone.floor),
                joinedload(Seat.allocations).joinedload(SeatAllocation.startup),
            )
        )
        result = await self._session.execute(query)
        return list(result.scalars().unique().all())

    async def get_active_allocations_map(
        self, building_id: UUID
    ) -> dict[UUID, SeatAllocation]:
        query = (
            select(SeatAllocation)
            .join(Seat, Seat.id == SeatAllocation.seat_id)
            .join(Zone, Zone.id == Seat.zone_id)
            .join(Floor, Floor.id == Zone.floor_id)
            .where(
                Floor.building_id == building_id,
                SeatAllocation.is_active.is_(True),
            )
            .options(joinedload(SeatAllocation.startup))
        )
        result = await self._session.execute(query)
        allocations = list(result.scalars().unique().all())
        return {alloc.seat_id: alloc for alloc in allocations}

    async def list_events(
        self,
        *,
        building_id: UUID | None = None,
        seat_id: UUID | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[OccupancyEvent], int]:
        query = select(OccupancyEvent)
        count_query = select(func.count()).select_from(OccupancyEvent)

        filters = []
        if seat_id:
            filters.append(OccupancyEvent.seat_id == seat_id)
        if since:
            filters.append(OccupancyEvent.detected_at >= since)
        if until:
            filters.append(OccupancyEvent.detected_at <= until)
        if building_id:
            query = (
                query.join(Seat, Seat.id == OccupancyEvent.seat_id)
                .join(Zone, Zone.id == Seat.zone_id)
                .join(Floor, Floor.id == Zone.floor_id)
            )
            count_query = (
                count_query.join(Seat, Seat.id == OccupancyEvent.seat_id)
                .join(Zone, Zone.id == Seat.zone_id)
                .join(Floor, Floor.id == Zone.floor_id)
            )
            filters.append(Floor.building_id == building_id)

        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))

        total = int((await self._session.execute(count_query)).scalar_one())
        result = await self._session.execute(
            query.order_by(desc(OccupancyEvent.detected_at)).limit(limit).offset(offset)
        )
        return list(result.scalars().all()), total

    async def count_occupied_by_startup(self, building_id: UUID) -> dict[UUID, int]:
        """Count currently occupied seats grouped by startup."""
        latest_events = await self.get_latest_events_for_building(building_id)
        allocations = await self.get_active_allocations_map(building_id)
        counts: dict[UUID, int] = {}
        for event in latest_events:
            if event.status != OccupancyStatus.OCCUPIED:
                continue
            alloc = allocations.get(event.seat_id)
            if alloc and alloc.startup_id:
                counts[alloc.startup_id] = counts.get(alloc.startup_id, 0) + 1
        return counts

    async def list_startups(self) -> list[Startup]:
        result = await self._session.execute(
            select(Startup).where(Startup.is_active.is_(True)).order_by(Startup.name)
        )
        return list(result.scalars().all())
