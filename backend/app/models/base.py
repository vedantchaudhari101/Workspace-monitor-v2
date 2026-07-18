"""Shared model mixins for UUID primary keys and timestamps.

Provides reusable mixins that add standardized UUID primary key columns
and created_at/updated_at timestamp columns to any SQLAlchemy ORM model.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDMixin:
    """Adds a UUID primary key column.

    Uses PostgreSQL's native UUID type for efficient storage and indexing.
    Generates UUIDv4 values by default for security and distributed
    system compatibility.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )


class TimestampMixin:
    """Adds created_at and updated_at timestamp columns.

    Both columns are timezone-aware and default to the current UTC time.
    The updated_at column automatically updates on row modification via
    SQLAlchemy's onupdate hook.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
