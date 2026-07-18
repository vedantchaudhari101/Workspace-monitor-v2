"""Live occupancy and event history business logic."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.exceptions import NotFoundError
from app.models.occupancy_event import OccupancyStatus
from app.repositories.building_repository import BuildingRepository
from app.repositories.occupancy_repository import OccupancyRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.occupancy import (
    FloorOccupancySummary,
    LiveOccupancyResponse,
    OccupancyEventResponse,
    SeatLiveStatus,
)


class OccupancyService:
    """Aggregates live seat states and historical occupancy events."""

    def __init__(self, session: AsyncSession) -> None:
        self._occupancy = OccupancyRepository(session)
        self._buildings = BuildingRepository(session)

    async def get_live_occupancy(self, building_id: UUID) -> LiveOccupancyResponse:
        building = await self._buildings.get_by_id(building_id)
        if not building:
            raise NotFoundError("Building", str(building_id))

        seats = await self._occupancy.list_seats_for_building(building_id)
        latest_events = await self._occupancy.get_latest_events_for_building(building_id)
        event_map = {e.seat_id: e for e in latest_events}
        allocations = await self._occupancy.get_active_allocations_map(building_id)

        seat_statuses: list[SeatLiveStatus] = []
        floor_stats: dict[UUID, dict] = {}

        for seat in seats:
            event = event_map.get(seat.id)
            status = event.status if event else OccupancyStatus.UNKNOWN
            alloc = allocations.get(seat.id)
            startup = alloc.startup if alloc else None
            zone = seat.zone
            floor = zone.floor

            seat_statuses.append(
                SeatLiveStatus(
                    seat_id=str(seat.id),
                    seat_label=seat.seat_label,
                    zone_id=str(zone.id),
                    zone_name=zone.name,
                    floor_id=str(floor.id),
                    floor_name=floor.name,
                    startup_id=str(startup.id) if startup else None,
                    startup_name=startup.name if startup else None,
                    status=status,
                    confidence=event.confidence if event else None,
                    detected_at=event.detected_at if event else None,
                )
            )

            if floor.id not in floor_stats:
                floor_stats[floor.id] = {
                    "floor_id": str(floor.id),
                    "floor_name": floor.name,
                    "total": 0,
                    "occupied": 0,
                    "vacant": 0,
                }
            floor_stats[floor.id]["total"] += 1
            if status == OccupancyStatus.OCCUPIED:
                floor_stats[floor.id]["occupied"] += 1
            elif status == OccupancyStatus.VACANT:
                floor_stats[floor.id]["vacant"] += 1

        occupied = sum(1 for s in seat_statuses if s.status == OccupancyStatus.OCCUPIED)
        vacant = sum(1 for s in seat_statuses if s.status == OccupancyStatus.VACANT)
        unknown = sum(1 for s in seat_statuses if s.status == OccupancyStatus.UNKNOWN)
        total = len(seat_statuses)
        rate = round((occupied / total * 100) if total else 0.0, 2)

        floors = [
            FloorOccupancySummary(
                floor_id=stats["floor_id"],
                floor_name=stats["floor_name"],
                total_seats=stats["total"],
                occupied_seats=stats["occupied"],
                vacant_seats=stats["vacant"],
                occupancy_rate=round(
                    (stats["occupied"] / stats["total"] * 100) if stats["total"] else 0.0, 2
                ),
            )
            for stats in floor_stats.values()
        ]

        return LiveOccupancyResponse(
            building_id=str(building.id),
            building_name=building.name,
            timestamp=datetime.now(timezone.utc),
            total_seats=total,
            occupied_seats=occupied,
            vacant_seats=vacant,
            unknown_seats=unknown,
            occupancy_rate=rate,
            floors=floors,
            seats=seat_statuses,
        )

    async def list_events(
        self,
        *,
        building_id: UUID | None = None,
        seat_id: UUID | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResponse[OccupancyEventResponse]:
        offset = (page - 1) * page_size
        events, total = await self._occupancy.list_events(
            building_id=building_id,
            seat_id=seat_id,
            since=since,
            until=until,
            limit=page_size,
            offset=offset,
        )
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return PaginatedResponse(
            items=[
                OccupancyEventResponse(
                    id=str(e.id),
                    seat_id=str(e.seat_id),
                    camera_id=str(e.camera_id),
                    status=e.status,
                    confidence=e.confidence,
                    detected_at=e.detected_at,
                    person_bbox=e.person_bbox,
                )
                for e in events
            ],
            meta=PaginationMeta(
                page=page,
                page_size=page_size,
                total_items=total,
                total_pages=total_pages,
            ),
        )
