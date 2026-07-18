"""Building query and utilization business logic."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.exceptions import NotFoundError
from app.models.occupancy_event import OccupancyStatus
from app.repositories.building_repository import BuildingRepository
from app.repositories.occupancy_repository import OccupancyRepository
from app.repositories.startup_repository import StartupRepository
from app.schemas.building import BuildingDetail, BuildingSummary, BuildingUtilization, FloorSummary


class BuildingService:
    """Building read operations and utilization summaries."""

    def __init__(self, session: AsyncSession) -> None:
        self._buildings = BuildingRepository(session)
        self._occupancy = OccupancyRepository(session)
        self._startups = StartupRepository(session)

    async def list_buildings(self) -> list[BuildingSummary]:
        buildings = await self._buildings.list_active()
        return [
            BuildingSummary(
                id=str(b.id),
                name=b.name,
                address=b.address,
                city=b.city,
                total_capacity=b.total_capacity,
                is_active=b.is_active,
            )
            for b in buildings
        ]

    async def get_building(self, building_id: UUID) -> BuildingDetail:
        building = await self._buildings.get_by_id(building_id)
        if not building:
            raise NotFoundError("Building", str(building_id))
        from app.schemas.building import CameraSummary
        return BuildingDetail(
            id=str(building.id),
            name=building.name,
            address=building.address,
            city=building.city,
            total_capacity=building.total_capacity,
            is_active=building.is_active,
            floors=[
                FloorSummary(
                    id=str(f.id),
                    name=f.name,
                    floor_number=f.floor_number,
                    total_capacity=f.total_capacity,
                    is_active=f.is_active,
                )
                for f in sorted(building.floors, key=lambda x: x.floor_number)
            ],
            cameras=[
                CameraSummary(
                    id=str(c.id),
                    name=c.name,
                    stream_url=c.stream_url,
                    floor_id=str(c.floor_id) if c.floor_id else None,
                    zone_id=str(c.zone_id) if c.zone_id else None,
                    is_active=c.is_active,
                )
                for c in building.cameras
            ],
        )

    async def get_utilization(self, building_id: UUID) -> BuildingUtilization:
        building = await self._buildings.get_by_id(building_id)
        if not building:
            raise NotFoundError("Building", str(building_id))

        seats = await self._occupancy.list_seats_for_building(building_id)
        latest_events = await self._occupancy.get_latest_events_for_building(building_id)
        event_map = {e.seat_id: e for e in latest_events}

        occupied = sum(
            1
            for seat in seats
            if event_map.get(seat.id) and event_map[seat.id].status == OccupancyStatus.OCCUPIED
        )
        total = len(seats)
        vacant = total - occupied
        rate = round((occupied / total * 100) if total else 0.0, 2)

        startups = await self._startups.list_all(active_only=True)
        allocated = sum(s.allocated_seats for s in startups)
        util_vs_alloc = round((occupied / allocated * 100) if allocated else 0.0, 2)

        return BuildingUtilization(
            building_id=str(building.id),
            building_name=building.name,
            total_seats=total,
            occupied_seats=occupied,
            vacant_seats=vacant,
            occupancy_rate=rate,
            allocated_seats=allocated,
            utilization_vs_allocation=util_vs_alloc,
        )
