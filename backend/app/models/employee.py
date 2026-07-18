"""Employee model representing individual workers within a startup.

Provides optional tracking of startup employees for more granular
occupancy analytics and seat assignment capabilities.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.startup import Startup


class Employee(UUIDMixin, TimestampMixin, Base):
    """Employee belonging to a tenant startup.

    Tracks individual employees within a startup for granular
    occupancy analytics. Each employee belongs to exactly one
    startup and has a unique email address.
    """

    __tablename__ = "employees"

    startup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("startups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    startup: Mapped[Startup] = relationship(
        "Startup", back_populates="employees", lazy="joined"
    )

    def __repr__(self) -> str:
        return (
            f"<Employee(id={self.id!r}, name={self.name!r}, "
            f"startup_id={self.startup_id!r})>"
        )
