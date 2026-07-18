"""Building and floor data access layer."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.building import Building
from app.models.floor import Floor


class BuildingRepository:
    """Read operations for buildings and floors."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> list[Building]:
        result = await self._session.execute(
            select(Building)
            .where(Building.is_active.is_(True))
            .order_by(Building.name)
        )
        return list(result.scalars().all())

    async def get_by_id(self, building_id: UUID) -> Building | None:
        result = await self._session.execute(
            select(Building)
            .options(selectinload(Building.floors), selectinload(Building.cameras))
            .where(Building.id == building_id)
        )
        return result.scalar_one_or_none()

    async def get_floor(self, floor_id: UUID) -> Floor | None:
        return await self._session.get(Floor, floor_id)
