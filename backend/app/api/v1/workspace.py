"""Workspace context and spatial map endpoints used by the frontend shell and explorer."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.config import get_settings
from app.models import Building, Camera, Floor, OccupancyEvent, Seat, Startup, Zone
from app.models.occupancy_event import DEMO_SOURCES
from app.services.seat_history import compute_analytics, load_seats
from app.api.v1.occupancy import snapshot_path
import os

router = APIRouter()


@router.get("/context", summary="Buildings, cameras, startups and runtime flags")
async def workspace_context(db: DbSession, _user: CurrentUser, building_id: UUID | None = Query(default=None)):
    from app.cv.capture import camera_manager

    settings = get_settings()
    buildings = (await db.execute(select(Building).where(Building.is_active.is_(True)).order_by(Building.created_at))).scalars().all()
    if not buildings:
        raise HTTPException(status_code=404, detail="No buildings configured.")
    current = next((b for b in buildings if b.id == building_id), buildings[0])

    cameras = (
        await db.execute(select(Camera).where(Camera.building_id == current.id).order_by(Camera.name))
    ).scalars().all()
    cam_rows = []
    for c in cameras:
        consumer = camera_manager.consumers.get(c.id)
        cfg = c.config or {}
        cam_rows.append({
            "id": str(c.id),
            "name": c.name,
            "zone_id": str(c.zone_id) if c.zone_id else None,
            "floor_id": str(c.floor_id) if c.floor_id else None,
            "is_active": c.is_active,
            "frame_w": cfg.get("frame_w") or c.resolution_width,
            "frame_h": cfg.get("frame_h") or c.resolution_height,
            "mode": consumer.mode if consumer else "idle",
            "status": consumer.status if consumer else "IDLE",
            "running": bool(consumer and consumer.running),
            "has_snapshot": os.path.isfile(snapshot_path(c.id)),
        })

    demo_seats = (await db.execute(select(func.count(Seat.id)).where(Seat.source == "SEED"))).scalar_one()
    demo_events = (
        await db.execute(select(func.count(OccupancyEvent.id)).where(OccupancyEvent.source.in_(DEMO_SOURCES)))
    ).scalar_one()
    startups = (await db.execute(select(Startup).where(Startup.is_active.is_(True)).order_by(Startup.name))).scalars().all()

    return {
        "building": {"id": str(current.id), "name": current.name, "city": current.city},
        "buildings": [{"id": str(b.id), "name": b.name} for b in buildings],
        "cameras": cam_rows,
        "startups": [{"id": str(s.id), "name": s.name, "allocated_seats": s.allocated_seats} for s in startups],
        "demo_mode": settings.DEMO_MODE,
        "demo_data_present": bool(demo_seats or demo_events),
        "pipeline": settings.CV_PIPELINE,
        "max_upload_mb": settings.MAX_UPLOAD_MB,
    }


@router.get("/map/{building_id}", summary="Floors, zones and seats with live status and utilization")
async def workspace_map(
    db: DbSession,
    _user: CurrentUser,
    building_id: UUID,
    range_hours: float = Query(default=24, gt=0, le=168),
    include_demo: bool | None = Query(default=None),
):
    """Spatial hierarchy for the explorer. Seat coordinates are camera-frame pixels."""
    demo = get_settings().DEMO_MODE if include_demo is None else include_demo
    analytics = await compute_analytics(db, building_id, range_hours, demo)
    stats = {r["seat_id"]: r for r in analytics["seat_stats"]}
    seats = await load_seats(db, building_id, demo)

    floors = (await db.execute(select(Floor).where(Floor.building_id == building_id).order_by(Floor.floor_number))).scalars().all()
    zones = (
        await db.execute(select(Zone).join(Floor, Floor.id == Zone.floor_id).where(Floor.building_id == building_id))
    ).scalars().unique().all()
    cameras = (await db.execute(select(Camera).where(Camera.building_id == building_id))).scalars().all()
    cam_by_zone = {c.zone_id: c for c in cameras if c.zone_id}

    seats_by_zone: dict = {}
    for s in seats:
        st = stats.get(str(s.id), {})
        seats_by_zone.setdefault(s.zone_id, []).append({
            "seat_id": str(s.id),
            "label": s.label,
            "source": s.source,
            "bbox": {"x": s.x, "y": s.y, "w": s.w, "h": s.h} if s.x is not None and s.w else None,
            "confidence": s.confidence,
            "startup_id": str(s.startup_id) if s.startup_id else None,
            "startup_name": s.startup_name,
            "allocation_id": str(s.allocation_id) if s.allocation_id else None,
            "status": st.get("current_status", "UNKNOWN"),
            "current_since": st.get("current_since"),
            "utilization_pct": st.get("utilization_pct"),
            "sessions": st.get("sessions"),
            "avg_session_s": st.get("avg_session_s"),
            "occupied_duration_s": st.get("occupied_duration_s"),
        })

    out = []
    for f in floors:
        fz = []
        for z in sorted([z for z in zones if z.floor_id == f.id], key=lambda z: z.name):
            zs = seats_by_zone.get(z.id, [])
            if not zs:
                continue
            cam = cam_by_zone.get(z.id)
            cfg = (cam.config or {}) if cam else {}
            from app.api.v1.occupancy import snapshot_path
            import os as _os

            fz.append({
                "zone_id": str(z.id),
                "name": z.name,
                "zone_type": z.zone_type.value if hasattr(z.zone_type, "value") else str(z.zone_type),
                "camera": {
                    "id": str(cam.id), "name": cam.name,
                    "frame_w": cfg.get("frame_w") or cam.resolution_width,
                    "frame_h": cfg.get("frame_h") or cam.resolution_height,
                    "has_snapshot": _os.path.isfile(snapshot_path(cam.id)),
                } if cam else None,
                "seats": zs,
            })
        if fz:
            out.append({"floor_id": str(f.id), "name": f.name, "floor_number": f.floor_number, "zones": fz})

    return {"window": analytics["window"], "sources": analytics["sources"], "floors": out}
