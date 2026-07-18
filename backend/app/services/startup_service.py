"""Startup CRUD and utilization business logic."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.exceptions import ConflictError, NotFoundError
from app.models.startup import Startup
from app.repositories.occupancy_repository import OccupancyRepository
from app.repositories.startup_repository import StartupRepository
from app.schemas.startup import (
    StartupCreate,
    StartupResponse,
    StartupUpdate,
    StartupUtilization,
)


class StartupService:
    """Startup management and utilization analytics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._startups = StartupRepository(session)
        self._occupancy = OccupancyRepository(session)

    async def list_startups(self, *, active_only: bool = False) -> list[StartupResponse]:
        startups = await self._startups.list_all(active_only=active_only)
        return [self._to_response(s) for s in startups]

    async def get_startup(self, startup_id: UUID) -> StartupResponse:
        startup = await self._require(startup_id)
        return self._to_response(startup)

    async def create_startup(self, payload: StartupCreate) -> StartupResponse:
        if await self._startups.get_by_name(payload.name):
            raise ConflictError(f"Startup '{payload.name}' already exists")
        startup = Startup(**payload.model_dump())
        created = await self._startups.create(startup)
        return self._to_response(created)

    async def update_startup(self, startup_id: UUID, payload: StartupUpdate) -> StartupResponse:
        startup = await self._require(startup_id)
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates and updates["name"] != startup.name:
            existing = await self._startups.get_by_name(updates["name"])
            if existing:
                raise ConflictError(f"Startup '{updates['name']}' already exists")
        for key, value in updates.items():
            setattr(startup, key, value)
        updated = await self._startups.update(startup)
        return self._to_response(updated)

    async def delete_startup(self, startup_id: UUID) -> None:
        startup = await self._require(startup_id)
        await self._startups.delete(startup)

    async def get_utilization(
        self, startup_id: UUID, *, building_id: UUID | None = None
    ) -> StartupUtilization:
        startup = await self._require(startup_id)
        occupied_map: dict[UUID, int] = {}

        if building_id:
            occupied_map = await self._occupancy.count_occupied_by_startup(building_id)
        else:
            # Aggregate across all buildings by summing per-building counts
            from app.repositories.building_repository import BuildingRepository

            buildings = await BuildingRepository(self._session).list_active()
            for building in buildings:
                partial = await self._occupancy.count_occupied_by_startup(building.id)
                for sid, count in partial.items():
                    occupied_map[sid] = occupied_map.get(sid, 0) + count

        occupied = occupied_map.get(startup_id, 0)
        allocated = startup.allocated_seats
        rate = round((occupied / allocated * 100) if allocated else 0.0, 2)
        monthly_value = allocated * startup.monthly_rate_per_seat

        if rate < 60:
            status = "UNDER_UTILIZED"
            leakage = max(0, allocated - occupied) * startup.monthly_rate_per_seat
        elif rate > 100:
            status = "OVER_UTILIZED"
            leakage = (occupied - allocated) * startup.monthly_rate_per_seat
        else:
            status = "OPTIMAL"
            leakage = max(0, allocated - occupied) * startup.monthly_rate_per_seat * 0.5

        return StartupUtilization(
            startup_id=str(startup.id),
            startup_name=startup.name,
            allocated_seats=allocated,
            occupied_seats=occupied,
            occupancy_rate=rate,
            monthly_contract_value=round(monthly_value, 2),
            estimated_revenue_leakage=round(leakage, 2),
            status=status,
        )

    async def _require(self, startup_id: UUID) -> Startup:
        startup = await self._startups.get_by_id(startup_id)
        if not startup:
            raise NotFoundError("Startup", str(startup_id))
        return startup

    @staticmethod
    def _to_response(startup: Startup) -> StartupResponse:
        return StartupResponse(
            id=str(startup.id),
            name=startup.name,
            contact_email=startup.contact_email,
            contact_phone=startup.contact_phone,
            allocated_seats=startup.allocated_seats,
            monthly_rate_per_seat=startup.monthly_rate_per_seat,
            contract_start=startup.contract_start,
            contract_end=startup.contract_end,
            is_active=startup.is_active,
            created_at=startup.created_at,
            updated_at=startup.updated_at,
        )
