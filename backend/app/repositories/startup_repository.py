"""Startup data access layer."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.startup import Startup


class StartupRepository:
    """CRUD operations for tenant startups."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self, *, active_only: bool = False) -> list[Startup]:
        query = select(Startup).order_by(Startup.name)
        if active_only:
            query = query.where(Startup.is_active.is_(True))
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, startup_id: UUID) -> Startup | None:
        return await self._session.get(Startup, startup_id)

    async def get_by_name(self, name: str) -> Startup | None:
        result = await self._session.execute(select(Startup).where(Startup.name == name))
        return result.scalar_one_or_none()

    async def count(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(Startup))
        return int(result.scalar_one())

    async def create(self, startup: Startup) -> Startup:
        self._session.add(startup)
        await self._session.flush()
        await self._session.refresh(startup)
        return startup

    async def update(self, startup: Startup) -> Startup:
        await self._session.flush()
        await self._session.refresh(startup)
        return startup

    async def delete(self, startup: Startup) -> None:
        await self._session.delete(startup)
