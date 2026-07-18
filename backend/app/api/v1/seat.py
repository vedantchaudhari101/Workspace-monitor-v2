"""Seat and Seat Allocation API routes."""

from __future__ import annotations

from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.exceptions import NotFoundError, ConflictError
from app.models.seat import Seat
from app.models.seat_allocation import SeatAllocation
from app.models.zone import Zone
from app.models.startup import Startup
from app.schemas.seat import (
    SeatCreate,
    SeatResponse,
    SeatUpdate,
    SeatAllocationCreate,
    SeatAllocationResponse,
    SeatAllocationUpdate,
)

router = APIRouter()

# ── Seat CRUD ───────────────────────────────────────────────────────────────

@router.post("", response_model=SeatResponse, status_code=status.HTTP_201_CREATED, summary="Create seat")
async def create_seat(db: DbSession, payload: SeatCreate, _user: CurrentUser) -> SeatResponse:
    """Create a new seat in a zone."""
    zone = await db.get(Zone, payload.zone_id)
    if not zone:
        raise NotFoundError("Zone", str(payload.zone_id))
        
    # Check if seat label already exists in the same zone
    existing = await db.execute(
        select(Seat).where(Seat.zone_id == payload.zone_id, Seat.seat_label == payload.seat_label)
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"Seat with label '{payload.seat_label}' already exists in zone '{payload.zone_id}'")

    seat = Seat(
        zone_id=payload.zone_id,
        seat_label=payload.seat_label,
        x_coordinate=payload.x_coordinate,
        y_coordinate=payload.y_coordinate,
        width=payload.width,
        height=payload.height,
        is_active=payload.is_active,
    )
    db.add(seat)
    await db.flush()
    await db.refresh(seat)
    return SeatResponse.model_validate(seat)


@router.get("", response_model=list[SeatResponse], summary="List seats")
async def list_seats(db: DbSession, _user: CurrentUser) -> list[SeatResponse]:
    """Return all seats."""
    result = await db.execute(select(Seat))
    return list(result.scalars().all())


@router.get("/{seat_id}", response_model=SeatResponse, summary="Get seat")
async def get_seat(seat_id: UUID, db: DbSession, _user: CurrentUser) -> SeatResponse:
    """Return details of a specific seat."""
    seat = await db.get(Seat, seat_id)
    if not seat:
        raise NotFoundError("Seat", str(seat_id))
    return SeatResponse.model_validate(seat)


@router.put("/{seat_id}", response_model=SeatResponse, summary="Update seat")
async def update_seat(
    seat_id: UUID, db: DbSession, payload: SeatUpdate, _user: CurrentUser
) -> SeatResponse:
    """Update seat details."""
    seat = await db.get(Seat, seat_id)
    if not seat:
        raise NotFoundError("Seat", str(seat_id))
        
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(seat, field, val)
        
    await db.flush()
    await db.refresh(seat)
    return SeatResponse.model_validate(seat)


@router.delete("/{seat_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete seat")
async def delete_seat(seat_id: UUID, db: DbSession, _user: CurrentUser) -> None:
    """Delete a seat."""
    seat = await db.get(Seat, seat_id)
    if not seat:
        raise NotFoundError("Seat", str(seat_id))
    await db.delete(seat)
    await db.flush()


# ── Seat Allocation CRUD ───────────────────────────────────────────────────

@router.post("/allocations", response_model=SeatAllocationResponse, status_code=status.HTTP_201_CREATED, summary="Allocate seat")
async def allocate_seat(db: DbSession, payload: SeatAllocationCreate, _user: CurrentUser) -> SeatAllocationResponse:
    """Allocate a seat to a startup."""
    seat = await db.get(Seat, payload.seat_id)
    if not seat:
        raise NotFoundError("Seat", str(payload.seat_id))
        
    startup = await db.get(Startup, payload.startup_id)
    if not startup:
        raise NotFoundError("Startup", str(payload.startup_id))

    # Check for active allocation for this seat
    existing_active = await db.execute(
        select(SeatAllocation).where(SeatAllocation.seat_id == payload.seat_id, SeatAllocation.is_active == True)
    )
    if existing_active.scalar_one_or_none():
        raise ConflictError(f"Seat '{payload.seat_id}' is already actively allocated")

    allocation = SeatAllocation(
        seat_id=payload.seat_id,
        startup_id=payload.startup_id,
        allocated_at=datetime.now(timezone.utc),
        is_active=True,
    )
    db.add(allocation)
    await db.flush()
    await db.refresh(allocation)
    return SeatAllocationResponse.model_validate(allocation)


@router.get("/allocations", response_model=list[SeatAllocationResponse], summary="List seat allocations")
async def list_allocations(db: DbSession, _user: CurrentUser) -> list[SeatAllocationResponse]:
    """Return all seat allocations."""
    result = await db.execute(select(SeatAllocation))
    return list(result.scalars().all())


@router.get("/allocations/{allocation_id}", response_model=SeatAllocationResponse, summary="Get seat allocation")
async def get_allocation(allocation_id: UUID, db: DbSession, _user: CurrentUser) -> SeatAllocationResponse:
    """Return details of a specific seat allocation."""
    allocation = await db.get(SeatAllocation, allocation_id)
    if not allocation:
        raise NotFoundError("SeatAllocation", str(allocation_id))
    return SeatAllocationResponse.model_validate(allocation)


@router.put("/allocations/{allocation_id}", response_model=SeatAllocationResponse, summary="Update seat allocation")
async def update_allocation(
    allocation_id: UUID, db: DbSession, payload: SeatAllocationUpdate, _user: CurrentUser
) -> SeatAllocationResponse:
    """Update seat allocation (e.g. to deallocate)."""
    allocation = await db.get(SeatAllocation, allocation_id)
    if not allocation:
        raise NotFoundError("SeatAllocation", str(allocation_id))
        
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(allocation, field, val)
        
    # If explicitly deallocating
    if payload.is_active is False and allocation.deallocated_at is None:
        allocation.deallocated_at = datetime.now(timezone.utc)
        
    await db.flush()
    await db.refresh(allocation)
    return SeatAllocationResponse.model_validate(allocation)


@router.delete("/allocations/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete seat allocation")
async def delete_allocation(allocation_id: UUID, db: DbSession, _user: CurrentUser) -> None:
    """Delete a seat allocation."""
    allocation = await db.get(SeatAllocation, allocation_id)
    if not allocation:
        raise NotFoundError("SeatAllocation", str(allocation_id))
    await db.delete(allocation)
    await db.flush()
