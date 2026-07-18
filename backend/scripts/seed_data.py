"""Seed data script for development and testing.

Populates the database with realistic sample data matching the project spec:
- 1 building (TechHub Tower, 100 seats)
- 3 floors, 6 zones, 100 seats
- 5 startups with seat allocations
- 3 cameras (one per floor)
- 1 admin user
- Sample occupancy events and snapshots

Usage:
    cd backend
    python -m scripts.seed_data

Idempotent: checks for existing data before inserting.
"""
from __future__ import annotations

import asyncio
import random
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.utils.security import hash_password
from app.database import Base
from app.models import (
    AuditLog,
    Building,
    Camera,
    Employee,
    Floor,
    OccupancyEvent,
    OccupancySnapshot,
    OccupancyStatus,
    PeriodType,
    Recommendation,
    RecommendationPriority,
    RecommendationStatus,
    RecommendationType,
    Seat,
    SeatAllocation,
    Startup,
    User,
    UserRole,
    Zone,
    ZoneType,
)


def _now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


async def seed_database() -> None:
    """Main seed function — creates all sample data."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create all tables (dev convenience)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("SUCCESS: Tables created / verified")

    async with session_factory() as session:
        # ── Check idempotency ────────────────────────────────────────
        existing = await session.execute(select(Building).limit(1))
        if existing.scalar_one_or_none():
            print("WARNING: Data already exists — skipping seed. Drop tables first to re-seed.")
            return

        # ── 1. Admin User ────────────────────────────────────────────
        print("Creating admin user...")
        admin_user = User(
            email="admin@workspace.dev",
            hashed_password=hash_password("Admin@12345"),
            full_name="Admin User",
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(admin_user)

        # ── 2. Building ──────────────────────────────────────────────
        print("Creating building...")
        building = Building(
            name="TechHub Tower",
            address="123 Innovation Drive",
            city="San Francisco",
            total_capacity=100,
            is_active=True,
            metadata_={"floors": 3, "year_built": 2022, "amenities": ["wifi", "cafeteria", "gym"]},
        )
        session.add(building)
        await session.flush()

        # ── 3. Floors ────────────────────────────────────────────────
        print("Creating floors...")
        floor_configs = [
            ("Ground Floor", 0, 35),
            ("First Floor", 1, 35),
            ("Second Floor", 2, 30),
        ]
        floors = []
        for name, number, capacity in floor_configs:
            floor = Floor(
                building_id=building.id,
                name=name,
                floor_number=number,
                total_capacity=capacity,
                is_active=True,
            )
            session.add(floor)
            floors.append(floor)
        await session.flush()

        # ── 4. Zones ────────────────────────────────────────────────
        print("Creating zones...")
        zone_configs = [
            # (floor_index, name, zone_type, capacity)
            (0, "Zone A", ZoneType.OPEN, 15),
            (0, "Zone B", ZoneType.OPEN, 20),
            (1, "Zone C", ZoneType.OPEN, 20),
            (1, "Zone D", ZoneType.PRIVATE, 15),
            (2, "Zone E", ZoneType.OPEN, 20),
            (2, "Zone F", ZoneType.MEETING, 10),
        ]
        zones = []
        for floor_idx, name, zone_type, capacity in zone_configs:
            zone = Zone(
                floor_id=floors[floor_idx].id,
                name=name,
                zone_type=zone_type,
                total_capacity=capacity,
                is_active=True,
            )
            session.add(zone)
            zones.append(zone)
        await session.flush()

        # ── 5. Seats ────────────────────────────────────────────────
        print("Creating 100 seats...")
        all_seats: list[Seat] = []
        zone_labels = ["A", "B", "C", "D", "E", "F"]

        for zone_idx, zone in enumerate(zones):
            capacity = [c for _, n, _, c in zone_configs if n == zone.name][0]
            label_prefix = zone_labels[zone_idx]

            for seat_num in range(1, capacity + 1):
                seat = Seat(
                    zone_id=zone.id,
                    seat_label=f"{label_prefix}-{seat_num:02d}",
                    # Mock pixel coordinates (grid layout)
                    x_coordinate=100.0 + (seat_num % 5) * 120.0,
                    y_coordinate=100.0 + (seat_num // 5) * 100.0,
                    width=80.0,
                    height=80.0,
                    is_active=True,
                )
                session.add(seat)
                all_seats.append(seat)
        await session.flush()
        print(f"   -> {len(all_seats)} seats created")

        # ── 6. Startups ──────────────────────────────────────────────
        print("Creating startups...")
        startup_configs = [
            ("Startup A", 20, 500.0, "alpha@startupa.com", "+1-555-0101"),
            ("Startup B", 20, 500.0, "beta@startupb.com", "+1-555-0102"),
            ("Startup C", 15, 450.0, "gamma@startupc.com", "+1-555-0103"),
            ("Startup D", 25, 550.0, "delta@startupd.com", "+1-555-0104"),
            ("Startup E", 20, 500.0, "epsilon@startupe.com", "+1-555-0105"),
        ]
        startups = []
        for name, seats, rate, email, phone in startup_configs:
            startup = Startup(
                name=name,
                contact_email=email,
                contact_phone=phone,
                allocated_seats=seats,
                monthly_rate_per_seat=rate,
                contract_start=date(2025, 1, 1),
                contract_end=date(2026, 12, 31),
                is_active=True,
            )
            session.add(startup)
            startups.append(startup)
        await session.flush()

        # ── 7. Employees (2-4 per startup) ───────────────────────────
        print("Creating employees...")
        employee_count = 0
        for startup in startups:
            num_employees = random.randint(8, 15)
            for i in range(1, num_employees + 1):
                emp = Employee(
                    startup_id=startup.id,
                    name=f"{startup.name} Employee {i}",
                    email=f"emp{i}@{startup.name.lower().replace(' ', '')}.com",
                    is_active=True,
                )
                session.add(emp)
                employee_count += 1
        await session.flush()
        print(f"   -> {employee_count} employees created")

        # ── 8. Seat Allocations ──────────────────────────────────────
        print("Allocating seats to startups...")
        seat_cursor = 0
        for startup in startups:
            for _ in range(startup.allocated_seats):
                if seat_cursor < len(all_seats):
                    allocation = SeatAllocation(
                        seat_id=all_seats[seat_cursor].id,
                        startup_id=startup.id,
                        allocated_at=_now() - timedelta(days=180),
                        deallocated_at=None,
                        is_active=True,
                    )
                    session.add(allocation)
                    seat_cursor += 1
        await session.flush()
        print(f"   -> {seat_cursor} seats allocated")

        # ── 9. Cameras ──────────────────────────────────────────────
        print("Creating cameras...")
        for i, floor in enumerate(floors):
            camera = Camera(
                building_id=building.id,
                name=f"Camera {i + 1} - {floor.name}",
                stream_url=f"rtsp://192.168.1.{10 + i}:554/stream",
                floor_id=floor.id,
                zone_id=None,
                is_active=True,
                resolution_width=1920,
                resolution_height=1080,
                fps=30,
                config={"codec": "h264", "bitrate": "4000k"},
            )
            session.add(camera)
        await session.flush()

        # Retrieve cameras for occupancy events
        cam_result = await session.execute(select(Camera))
        cameras = cam_result.scalars().all()

        # ── 10. Occupancy Events (today's data) ─────────────────────
        print("Generating occupancy events...")
        today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
        event_count = 0

        # Simulate hourly occupancy patterns (8 AM to 6 PM)
        hourly_occupancy_pct = [23, 45, 78, 82, 65, 58, 71, 76, 68, 42, 18]

        for hour_offset, occ_pct in enumerate(hourly_occupancy_pct):
            detection_time = today + timedelta(hours=8 + hour_offset)
            num_occupied = int(len(all_seats) * occ_pct / 100)
            occupied_seats = random.sample(all_seats, min(num_occupied, len(all_seats)))

            for seat in all_seats[:50]:  # Limit to 50 seats per hour for seed data
                is_occupied = seat in occupied_seats
                camera = cameras[0] if len(cameras) > 0 else cameras[0]

                event = OccupancyEvent(
                    seat_id=seat.id,
                    camera_id=camera.id,
                    status=OccupancyStatus.OCCUPIED if is_occupied else OccupancyStatus.VACANT,
                    confidence=round(random.uniform(0.75, 0.99), 3),
                    detected_at=detection_time + timedelta(seconds=random.randint(0, 59)),
                    person_bbox={"x": seat.x_coordinate, "y": seat.y_coordinate, "w": 60, "h": 80}
                    if is_occupied
                    else None,
                )
                session.add(event)
                event_count += 1

        await session.flush()
        print(f"   -> {event_count} occupancy events created")

        # ── 11. Occupancy Snapshots ──────────────────────────────────
        print("Creating occupancy snapshots...")
        snapshot_count = 0
        for hour_offset, occ_pct in enumerate(hourly_occupancy_pct):
            snapshot_time = today + timedelta(hours=8 + hour_offset)
            occupied = int(100 * occ_pct / 100)

            snapshot = OccupancySnapshot(
                building_id=building.id,
                floor_id=None,
                startup_id=None,
                snapshot_time=snapshot_time,
                total_seats=100,
                occupied_seats=occupied,
                occupancy_rate=float(occ_pct),
                period_type=PeriodType.HOURLY,
                metadata_={"peak_zone": random.choice(zone_labels), "avg_confidence": 0.92},
            )
            session.add(snapshot)
            snapshot_count += 1

            # Per-startup snapshots
            for startup in startups:
                startup_occ_rate = occ_pct * random.uniform(0.5, 1.3)
                startup_occ_rate = min(startup_occ_rate, 100.0)
                startup_occupied = int(startup.allocated_seats * startup_occ_rate / 100)

                snapshot_s = OccupancySnapshot(
                    building_id=building.id,
                    floor_id=None,
                    startup_id=startup.id,
                    snapshot_time=snapshot_time,
                    total_seats=startup.allocated_seats,
                    occupied_seats=startup_occupied,
                    occupancy_rate=round(startup_occ_rate, 1),
                    period_type=PeriodType.HOURLY,
                )
                session.add(snapshot_s)
                snapshot_count += 1

        await session.flush()
        print(f"   -> {snapshot_count} snapshots created")

        # ── 12. Sample Recommendations ───────────────────────────────
        print("Creating sample recommendations...")
        rec1 = Recommendation(
            startup_id=startups[2].id,  # Startup C — under-utilized
            recommendation_type=RecommendationType.REDUCTION,
            title="Reduce Startup C allocation by 5 seats",
            description=(
                "Startup C consistently uses only 8 of 15 allocated seats (53% utilization). "
                "Recommend reducing allocation to 10 seats, saving $2,250/month in revenue leakage. "
                "The freed seats can be reallocated to Startup D which is near capacity."
            ),
            priority=RecommendationPriority.HIGH,
            status=RecommendationStatus.PENDING,
            impact_seats=5,
            impact_revenue=2250.0,
            data={"current_util": 53, "recommended_seats": 10, "current_seats": 15},
        )
        rec2 = Recommendation(
            startup_id=startups[3].id,  # Startup D — near capacity
            recommendation_type=RecommendationType.EXPANSION,
            title="Expand Startup D allocation by 3 seats",
            description=(
                "Startup D is at 88% utilization (22/25 seats) and trending upward. "
                "Recommend expanding allocation to 28 seats to accommodate growth. "
                "Additional revenue: $1,650/month."
            ),
            priority=RecommendationPriority.MEDIUM,
            status=RecommendationStatus.PENDING,
            impact_seats=3,
            impact_revenue=1650.0,
            data={"current_util": 88, "recommended_seats": 28, "current_seats": 25},
        )
        session.add_all([rec1, rec2])

        # ── 13. Audit Log Entry ──────────────────────────────────────
        print("Creating audit log entry...")
        audit = AuditLog(
            user_id=admin_user.id,
            action="SYSTEM_SEEDED",
            entity_type="system",
            entity_id=None,
            details={"seed_version": "1.0", "tables_seeded": 13},
            ip_address="127.0.0.1",
        )
        session.add(audit)

        # ── Commit everything ────────────────────────────────────────
        await session.commit()
        print("\n" + "=" * 60)
        print("Database seeded successfully!")
        print("=" * 60)
        print(f"  Users:              1")
        print(f"  Buildings:          1")
        print(f"  Floors:             {len(floors)}")
        print(f"  Zones:              {len(zones)}")
        print(f"  Seats:              {len(all_seats)}")
        print(f"  Startups:           {len(startups)}")
        print(f"  Employees:          {employee_count}")
        print(f"  Seat Allocations:   {seat_cursor}")
        print(f"  Cameras:            {len(cameras)}")
        print(f"  Occupancy Events:   {event_count}")
        print(f"  Snapshots:          {snapshot_count}")
        print(f"  Recommendations:    2")
        print(f"  Audit Logs:         1")
        print("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_database())
