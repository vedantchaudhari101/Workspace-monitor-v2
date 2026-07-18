"""Startup and seat allocation schemas."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class StartupBase(ORMModel):
    name: str = Field(min_length=1, max_length=255)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=50)
    allocated_seats: int = Field(ge=0)
    monthly_rate_per_seat: float = Field(ge=0)
    contract_start: date | None = None
    contract_end: date | None = None
    is_active: bool = True


class StartupCreate(StartupBase):
    pass


class StartupUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=50)
    allocated_seats: int | None = Field(default=None, ge=0)
    monthly_rate_per_seat: float | None = Field(default=None, ge=0)
    contract_start: date | None = None
    contract_end: date | None = None
    is_active: bool | None = None


class StartupResponse(StartupBase):
    id: str
    created_at: datetime
    updated_at: datetime


class StartupUtilization(ORMModel):
    startup_id: str
    startup_name: str
    allocated_seats: int
    occupied_seats: int
    occupancy_rate: float = Field(description="Percentage 0-100")
    monthly_contract_value: float
    estimated_revenue_leakage: float = Field(
        description="Monthly revenue lost from under-utilized seats"
    )
    status: str = Field(description="UNDER_UTILIZED | OPTIMAL | OVER_UTILIZED")


# --- Employee Schemas ---

class EmployeeCreate(BaseModel):
    startup_id: UUID
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    is_active: bool = True


class EmployeeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    is_active: bool | None = None


class EmployeeResponse(ORMModel):
    id: UUID
    startup_id: UUID
    name: str
    email: EmailStr | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
