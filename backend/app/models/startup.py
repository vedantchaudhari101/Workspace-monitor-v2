"""Startup model representing tenant startups in the coworking space.

Startups are the primary tenants that occupy seats within the workspace.
Each startup has a contract with allocated seats and a per-seat monthly
rate used for revenue calculations.
"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.recommendation import Recommendation
    from app.models.seat_allocation import SeatAllocation


class Startup(UUIDMixin, TimestampMixin, Base):
    """Tenant startup occupying workspace seats.

    Represents a company that rents seats in the coworking space.
    Tracks contract details including allocated seats, monthly rate,
    and contract period. Links to employees, seat allocations, and
    AI-generated recommendations for seat optimization.
    """

    __tablename__ = "startups"

    name: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    contact_email: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    contact_phone: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    allocated_seats: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    monthly_rate_per_seat: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    contract_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    employees: Mapped[list[Employee]] = relationship(
        "Employee", back_populates="startup", lazy="selectin",
        cascade="all, delete-orphan",
    )
    seat_allocations: Mapped[list[SeatAllocation]] = relationship(
        "SeatAllocation", back_populates="startup", lazy="selectin",
        cascade="all, delete-orphan",
    )
    recommendations: Mapped[list[Recommendation]] = relationship(
        "Recommendation", back_populates="startup", lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Startup(id={self.id!r}, name={self.name!r}, "
            f"allocated_seats={self.allocated_seats!r}, "
            f"is_active={self.is_active!r})>"
        )
