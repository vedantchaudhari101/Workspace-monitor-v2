"""Startup and Employee API routes."""

from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, DbSession, ManagerOrAdmin
from app.api.exceptions import NotFoundError, ConflictError
from app.models.startup import Startup
from app.models.employee import Employee
from app.schemas.common import MessageResponse
from app.schemas.startup import (
    StartupCreate,
    StartupResponse,
    StartupUpdate,
    StartupUtilization,
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
)
from app.services.startup_service import StartupService

router = APIRouter()

# ── Stats Endpoint ──────────────────────────────────────────────────────────

@router.get("/stats", response_model=list[StartupUtilization], summary="All startups utilization statistics")
async def get_all_stats(db: DbSession, _user: CurrentUser) -> list[StartupUtilization]:
    """Return seat allocation counts and utilization details for each startup."""
    service = StartupService(db)
    startups = await service.list_startups(active_only=False)
    
    stats_list = []
    for s in startups:
        util = await service.get_utilization(UUID(s.id))
        stats_list.append(util)
        
    return stats_list


# ── Startup CRUD ────────────────────────────────────────────────────────────

@router.get("", response_model=list[StartupResponse], summary="List startups")
async def list_startups(
    db: DbSession,
    _user: CurrentUser,
    active_only: bool = Query(default=False),
) -> list[StartupResponse]:
    """Return all tenant startups."""
    return await StartupService(db).list_startups(active_only=active_only)


@router.get("/{startup_id}", response_model=StartupResponse, summary="Get startup")
async def get_startup(
    startup_id: UUID,
    db: DbSession,
    _user: CurrentUser,
) -> StartupResponse:
    """Return a single startup by ID."""
    return await StartupService(db).get_startup(startup_id)


@router.get(
    "/{startup_id}/utilization",
    response_model=StartupUtilization,
    summary="Startup utilization metrics",
)
async def startup_utilization(
    startup_id: UUID,
    db: DbSession,
    _user: CurrentUser,
    building_id: UUID | None = Query(default=None),
) -> StartupUtilization:
    """Return occupancy and revenue leakage metrics for a startup."""
    return await StartupService(db).get_utilization(startup_id, building_id=building_id)


@router.post(
    "",
    response_model=StartupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create startup",
)
async def create_startup(
    db: DbSession,
    _user: ManagerOrAdmin,
    payload: StartupCreate,
) -> StartupResponse:
    """Create a new tenant startup."""
    return await StartupService(db).create_startup(payload)


@router.patch("/{startup_id}", response_model=StartupResponse, summary="Update startup")
async def update_startup(
    startup_id: UUID,
    db: DbSession,
    _user: ManagerOrAdmin,
    payload: StartupUpdate,
) -> StartupResponse:
    """Update an existing startup."""
    return await StartupService(db).update_startup(startup_id, payload)


@router.delete(
    "/{startup_id}",
    response_model=MessageResponse,
    summary="Delete startup",
)
async def delete_startup(
    startup_id: UUID,
    db: DbSession,
    _admin: AdminUser,
) -> MessageResponse:
    """Permanently delete a startup (admin only)."""
    await StartupService(db).delete_startup(startup_id)
    return MessageResponse(message="Startup deleted successfully")


# ── Employee CRUD ───────────────────────────────────────────────────────────

@router.post("/employees", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED, summary="Create employee")
async def create_employee(db: DbSession, payload: EmployeeCreate, _user: CurrentUser) -> EmployeeResponse:
    """Create a new employee belonging to a startup."""
    startup = await db.get(Startup, payload.startup_id)
    if not startup:
        raise NotFoundError("Startup", str(payload.startup_id))
        
    if payload.email:
        # Check unique email constraint
        existing = await db.execute(
            select(Employee).where(Employee.email == payload.email)
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Employee email '{payload.email}' is already registered")

    employee = Employee(
        startup_id=payload.startup_id,
        name=payload.name,
        email=payload.email,
        is_active=payload.is_active,
    )
    db.add(employee)
    await db.flush()
    await db.refresh(employee)
    return EmployeeResponse.model_validate(employee)


@router.get("/employees", response_model=list[EmployeeResponse], summary="List employees")
async def list_employees(
    db: DbSession,
    _user: CurrentUser,
    startup_id: UUID | None = Query(default=None),
) -> list[EmployeeResponse]:
    """Return list of employees, optionally filtered by startup_id."""
    stmt = select(Employee)
    if startup_id:
        stmt = stmt.where(Employee.startup_id == startup_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/employees/{employee_id}", response_model=EmployeeResponse, summary="Get employee")
async def get_employee(employee_id: UUID, db: DbSession, _user: CurrentUser) -> EmployeeResponse:
    """Return details of a specific employee."""
    employee = await db.get(Employee, employee_id)
    if not employee:
        raise NotFoundError("Employee", str(employee_id))
    return EmployeeResponse.model_validate(employee)


@router.put("/employees/{employee_id}", response_model=EmployeeResponse, summary="Update employee")
async def update_employee(
    employee_id: UUID, db: DbSession, payload: EmployeeUpdate, _user: CurrentUser
) -> EmployeeResponse:
    """Update employee details."""
    employee = await db.get(Employee, employee_id)
    if not employee:
        raise NotFoundError("Employee", str(employee_id))
        
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(employee, field, val)
        
    await db.flush()
    await db.refresh(employee)
    return EmployeeResponse.model_validate(employee)


@router.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete employee")
async def delete_employee(employee_id: UUID, db: DbSession, _user: CurrentUser) -> None:
    """Delete an employee."""
    employee = await db.get(Employee, employee_id)
    if not employee:
        raise NotFoundError("Employee", str(employee_id))
    await db.delete(employee)
    await db.flush()
