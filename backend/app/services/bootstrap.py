"""First-run bootstrap.

Guarantees the minimum structure the product needs to accept a video:
an admin account, one building with a floor, and an active camera whose
detected seats have a zone to live in. Nothing here invents occupancy data.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Building, Camera, Floor, User, UserRole, Zone, ZoneType
from app.models.analysis_session import AnalysisSession, SessionStatus
from app.utils.logger import get_logger
from app.utils.security import hash_password, verify_password

logger = get_logger(__name__)


async def ensure_camera_zone(session: AsyncSession, camera: Camera) -> uuid.UUID:
    """Return the zone that holds this camera's detected seats, creating it if needed.

    Seeded cameras were created with ``zone_id=None``; in the original code
    that meant detected seats were never persisted, so no history was stored.
    """
    if camera.zone_id:
        return camera.zone_id

    floor_id = camera.floor_id
    if floor_id is None:
        floor_id = (
            await session.execute(
                select(Floor.id).where(Floor.building_id == camera.building_id).order_by(Floor.floor_number).limit(1)
            )
        ).scalar_one_or_none()
        if floor_id is None:
            floor = Floor(building_id=camera.building_id, name="Floor 1", floor_number=1, total_capacity=0)
            session.add(floor)
            await session.flush()
            floor_id = floor.id
        camera.floor_id = floor_id

    zone = Zone(floor_id=floor_id, name=f"{camera.name} view", zone_type=ZoneType.OPEN, total_capacity=0)
    session.add(zone)
    await session.flush()
    camera.zone_id = zone.id
    await session.flush()
    return zone.id


async def bootstrap(session: AsyncSession) -> None:
    """Create the admin user and a default workspace when the database is empty."""
    settings = get_settings()

    # The configured admin account always matches ADMIN_EMAIL / ADMIN_PASSWORD,
    # so changing the password in the environment and restarting resets it.
    admin = (await session.execute(select(User).where(User.email == settings.ADMIN_EMAIL))).scalar_one_or_none()
    if admin is None:
        session.add(
            User(
                email=settings.ADMIN_EMAIL,
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                full_name="Workspace Admin",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        logger.info(f"Bootstrap: created admin user {settings.ADMIN_EMAIL}")
    else:
        if not admin.hashed_password or not verify_password(settings.ADMIN_PASSWORD, admin.hashed_password):
            admin.hashed_password = hash_password(settings.ADMIN_PASSWORD)
            logger.info(f"Bootstrap: admin password updated from configuration for {settings.ADMIN_EMAIL}")
        admin.is_active = True
        admin.role = UserRole.ADMIN

    building = (
        await session.execute(select(Building).where(Building.is_active.is_(True)).order_by(Building.created_at).limit(1))
    ).scalar_one_or_none()
    if building is None:
        building = Building(name="Main Workspace", total_capacity=0, is_active=True, metadata_={})
        session.add(building)
        await session.flush()
        logger.info("Bootstrap: created default building")

    camera = (
        await session.execute(
            select(Camera).where(Camera.building_id == building.id, Camera.is_active.is_(True)).limit(1)
        )
    ).scalar_one_or_none()
    if camera is None:
        camera = Camera(
            building_id=building.id,
            name="Camera 1",
            stream_url="upload://",
            is_active=True,
            fps=30,
            config={"source_type": "idle"},
        )
        session.add(camera)
        await session.flush()
        logger.info("Bootstrap: created default camera")

    await ensure_camera_zone(session, camera)

    # Sessions that were running when the server stopped cannot resume.
    stale = (
        await session.execute(
            select(AnalysisSession).where(
                AnalysisSession.status.in_(
                    [SessionStatus.UPLOADED.value, SessionStatus.CALIBRATING.value, SessionStatus.TRACKING.value]
                )
            )
        )
    ).scalars().all()
    for s in stale:
        s.status = SessionStatus.STOPPED.value
        s.error = "Interrupted by a server restart."

    await session.commit()
