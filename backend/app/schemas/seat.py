"""Seat and Seat Allocation schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class SeatBase(ORMModel):
    seat_label: str = Field(min_length=1, max_length=50)
    x_coordinate: float | None = None
    y_coordinate: float | None = None
    width: float | None = None
    height: float | None = None
    is_active: bool = True


class SeatCreate(SeatBase):
    zone_id: UUID


class SeatUpdate(BaseModel):
    seat_label: str | None = Field(default=None, min_length=1, max_length=50)
    x_coordinate: float | None = None
    y_coordinate: float | None = None
    width: float | None = None
    height: float | None = None
    is_active: bool | None = None


class SeatResponse(SeatBase):
    id: UUID
    zone_id: UUID
    created_at: datetime
    updated_at: datetime


class SeatAllocationBase(ORMModel):
    seat_id: UUID
    startup_id: UUID
    allocated_at: datetime
    deallocated_at: datetime | None = None
    is_active: bool = True


class SeatAllocationCreate(BaseModel):
    seat_id: UUID
    startup_id: UUID


class SeatAllocationUpdate(BaseModel):
    deallocated_at: datetime | None = None
    is_active: bool | None = None


class SeatAllocationResponse(SeatAllocationBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
