"""Async SQLAlchemy Database Setup.

Provides the async engine, session factory, declarative base, and helpers
for obtaining scoped database sessions inside request handlers.

Usage::

    from app.database import get_db_session, Base

    async for session in get_db_session():
        result = await session.execute(...)
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

# ── Engine & Session Factory ────────────────────────────────────────────────

settings = get_settings()

if settings.USE_SQLITE:
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        connect_args={"timeout": 60.0},
    )
else:
    engine = create_async_engine(
        settings.database_url,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        echo=False,
    )

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Declarative Base ────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    All domain models must inherit from this base so that Alembic
    auto-generates migrations from a single metadata registry.
    """

    pass


# ── Session Helpers ─────────────────────────────────────────────────────────


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session with automatic commit/rollback.

    Intended for use as a FastAPI dependency::

        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db_session)):
            ...

    On successful completion the transaction is committed; on any exception
    it is rolled back and the exception is re-raised.
    """
    session: AsyncSession = async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db() -> None:
    """Create all tables defined in :attr:`Base.metadata`.

    This is a **development convenience** — in production, use Alembic
    migrations instead.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
