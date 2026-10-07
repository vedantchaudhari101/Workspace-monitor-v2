"""Time-weighted occupancy analytics built from stored state changes.

Replaces the original event-count arithmetic (OCCUPIED events ÷ all events)
with measured time: each seat's events are turned into intervals and every
duration, utilization and session figure comes from those intervals.

Data provenance: by default only ``source=VIDEO`` events (real CV output) are
used. ``include_demo=True`` adds seeded / simulated / legacy data, and the
response always says which sources were included.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.intervals import (
    OCCUPIED,
    UNKNOWN,
    VACANT,
    Interval,
    accumulate_by_key,
    bucket_timeline,
    max_concurrent,
    build_intervals,
    hour_of_day_key,
    peak_window,
    seat_stats,
)
from app.models import Camera, Floor, OccupancyEvent, Seat, SeatAllocation, Startup, Zone
from app.models.analysis_session import AnalysisSession
from app.models.occupancy_event import DEMO_SOURCES, EventSource
from app.utils.timefmt import iso_utc


def _ts(dt: datetime) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _iso(t: Optional[float]) -> Optional[str]:
    if t is None:
        return None
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat()


def _status(v: Any) -> str:
    return v.value if hasattr(v, "value") else str(v)


def bucket_for_range(range_hours: float) -> int:
    if range_hours <= 1:
        return 60
    if range_hours <= 6:
        return 300
    if range_hours <= 24:
        return 900
    if range_hours <= 72:
        return 3600
    return 3 * 3600


@dataclass
class SeatInfo:
    id: UUID
    label: str
    zone_id: UUID
    zone_name: str
    floor_id: UUID
    floor_name: str
    source: str
    is_active: bool
    x: Optional[float]
    y: Optional[float]
    w: Optional[float]
    h: Optional[float]
    confidence: Optional[float]
    startup_id: Optional[UUID] = None
    startup_name: Optional[str] = None
    allocation_id: Optional[UUID] = None


async def load_seats(
    db: AsyncSession,
    building_id: UUID,
    include_demo: bool,
    include_inactive: bool = False,
    seat_id: Optional[UUID] = None,
) -> List[SeatInfo]:
    q = (
        select(Seat, Zone.name, Floor.id, Floor.name)
        .join(Zone, Zone.id == Seat.zone_id)
        .join(Floor, Floor.id == Zone.floor_id)
        .where(Floor.building_id == building_id)
    )
    if not include_inactive:
        q = q.where(Seat.is_active.is_(True))
    if not include_demo:
        q = q.where(Seat.source != "SEED")
    if seat_id is not None:
        q = q.where(Seat.id == seat_id)
    rows = (await db.execute(q)).unique().all()

    seats = [
        SeatInfo(
            id=s.id, label=s.seat_label, zone_id=s.zone_id, zone_name=zname,
            floor_id=fid, floor_name=fname, source=s.source, is_active=s.is_active,
            x=s.x_coordinate, y=s.y_coordinate, w=s.width, h=s.height, confidence=s.confidence,
        )
        for s, zname, fid, fname in rows
    ]
    if not seats:
        return seats

    allocs = (
        await db.execute(
            select(SeatAllocation.id, SeatAllocation.seat_id, Startup.id, Startup.name)
            .join(Startup, Startup.id == SeatAllocation.startup_id)
            .where(SeatAllocation.seat_id.in_([s.id for s in seats]), SeatAllocation.is_active.is_(True))
        )
    ).all()
    by_seat = {seat: (aid, sid, name) for aid, seat, sid, name in allocs}
    for s in seats:
        if s.id in by_seat:
            s.allocation_id, s.startup_id, s.startup_name = by_seat[s.id]

    def sort_key(s: SeatInfo):
        digits = "".join(ch for ch in s.label if ch.isdigit())
        return (s.floor_name, s.zone_name, s.label.rstrip("0123456789"), int(digits) if digits else 0, s.label)

    return sorted(seats, key=sort_key)


def _source_filter(include_demo: bool):
    return None if include_demo else (OccupancyEvent.source == EventSource.VIDEO.value)


async def load_intervals(
    db: AsyncSession,
    seat_ids: List[UUID],
    since: datetime,
    until: datetime,
    include_demo: bool,
) -> Dict[UUID, List[Interval]]:
    """Intervals per seat across [since, until]."""
    if not seat_ids:
        return {}
    src = _source_filter(include_demo)

    # State in force at `since`: the latest event before the window.
    latest_q = (
        select(OccupancyEvent.seat_id, func.max(OccupancyEvent.detected_at).label("max_dt"))
        .where(OccupancyEvent.seat_id.in_(seat_ids), OccupancyEvent.detected_at < since)
    )
    if src is not None:
        latest_q = latest_q.where(src)
    latest = latest_q.group_by(OccupancyEvent.seat_id).subquery()
    init_q = select(OccupancyEvent.seat_id, OccupancyEvent.status).join(
        latest,
        and_(OccupancyEvent.seat_id == latest.c.seat_id, OccupancyEvent.detected_at == latest.c.max_dt),
    )
    if src is not None:
        init_q = init_q.where(src)
    initial = {sid: _status(st) for sid, st in (await db.execute(init_q)).all()}

    ev_q = (
        select(OccupancyEvent.seat_id, OccupancyEvent.detected_at, OccupancyEvent.status)
        .where(
            OccupancyEvent.seat_id.in_(seat_ids),
            OccupancyEvent.detected_at >= since,
            OccupancyEvent.detected_at < until,
        )
        .order_by(OccupancyEvent.detected_at)
    )
    if src is not None:
        ev_q = ev_q.where(src)
    per_seat: Dict[UUID, List[Tuple[float, str]]] = defaultdict(list)
    for sid, dt, st in (await db.execute(ev_q)).all():
        per_seat[sid].append((_ts(dt), _status(st)))

    s0, s1 = _ts(since), _ts(until)
    return {sid: build_intervals(per_seat.get(sid, []), s0, s1, initial.get(sid)) for sid in seat_ids}


async def sources_present(db: AsyncSession, seat_ids: List[UUID], since: datetime) -> Dict[str, bool]:
    if not seat_ids:
        return {"video": False, "demo": False}
    rows = (
        await db.execute(
            select(OccupancyEvent.source, func.count(OccupancyEvent.id))
            .where(OccupancyEvent.seat_id.in_(seat_ids), OccupancyEvent.detected_at >= since)
            .group_by(OccupancyEvent.source)
        )
    ).all()
    present = {src for src, n in rows if n}
    return {"video": EventSource.VIDEO.value in present, "demo": bool(present & set(DEMO_SOURCES))}


async def _performance(db: AsyncSession, building_id: UUID) -> Dict[str, Any]:
    """Real pipeline metrics: the active run if any, otherwise the latest stored session."""
    from app.cv.capture import camera_manager

    cams = (await db.execute(select(Camera.id).where(Camera.building_id == building_id))).scalars().all()
    for cid in cams:
        c = camera_manager.consumers.get(cid)
        if c is not None and c.mode == "video" and c.running:
            fps = c.video_fps or 0
            return {
                "source": "live",
                "fps": c.inference_fps(),
                "frames_processed": c.current_frame_index,
                "avg_processing_time": round(c.inference_ms, 1) if c.inference_ms else None,
                "total_video_length": round(c.total_frames / fps, 1) if fps else None,
                "analysis_duration": round((datetime.now(timezone.utc) - c.started_at).total_seconds(), 1) if c.started_at else None,
            }
    if not cams:
        return {"source": None}
    row = (
        await db.execute(
            select(AnalysisSession)
            .where(AnalysisSession.camera_id.in_(cams), AnalysisSession.completed_at.isnot(None))
            .order_by(AnalysisSession.completed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return {"source": None}
    perf = (row.summary or {}).get("performance") or {}
    return {
        "source": "last_session",
        "session_id": str(row.id),
        "fps": perf.get("inference_fps"),
        "frames_processed": row.frames_processed,
        "avg_processing_time": row.avg_inference_ms,
        "total_video_length": row.video_duration_s,
        "analysis_duration": perf.get("processing_s"),
    }


async def compute_analytics(
    db: AsyncSession,
    building_id: UUID,
    range_hours: float = 24,
    include_demo: bool = False,
    tz_offset_minutes: int = 0,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=range_hours)
    s0, s1 = _ts(since), _ts(now)
    bucket_s = bucket_for_range(range_hours)

    seats = await load_seats(db, building_id, include_demo)
    seat_ids = [s.id for s in seats]
    intervals = await load_intervals(db, seat_ids, since, now, include_demo)
    present = await sources_present(db, seat_ids, since)

    rows: List[Dict[str, Any]] = []
    for s in seats:
        st = seat_stats(intervals.get(s.id, []))
        rows.append({
            "seat_id": str(s.id),
            "seat_label": s.label,
            "zone": s.zone_name,
            "floor": s.floor_name,
            "source": s.source,
            "startup_id": str(s.startup_id) if s.startup_id else None,
            "startup_name": s.startup_name,
            "utilization_pct": st["utilization_pct"],
            "occupied_duration_s": st["occupied_s"],
            "vacant_duration_s": st["vacant_s"],
            "observed_duration_s": st["observed_s"],
            "occupancy_count": st["sessions"],
            "sessions": st["sessions"],
            "avg_session_s": st["avg_session_s"],
            "longest_session_s": st["longest_session_s"],
            "first_occupied": _iso(st["first_occupied"]),
            "last_occupied": _iso(st["last_occupied"]),
            "current_status": st["current_status"],
            "current_since": _iso(st["current_since"]),
        })

    timeline_raw = bucket_timeline({sid: iv for sid, iv in intervals.items()}, s0, s1, bucket_s)
    observed_pcts = [b["occupancy_pct"] for b in timeline_raw if b["occupancy_pct"] is not None]

    total_occ = sum(r["occupied_duration_s"] for r in rows)
    total_obs = sum(r["observed_duration_s"] for r in rows)
    avg_pct = round(total_occ / total_obs * 100.0, 1) if total_obs > 0 else None

    occupied_now = sum(1 for r in rows if r["current_status"] == OCCUPIED)
    vacant_now = sum(1 for r in rows if r["current_status"] == VACANT)
    observed_now = occupied_now + vacant_now

    peak_bucket = max(timeline_raw, key=lambda b: b["occupied"], default=None)
    peak_seats, peak_seats_at = max_concurrent(intervals)
    window = peak_window(timeline_raw, bucket_s)

    # Hour-of-day profile (viewer's local time).
    hour_fn = hour_of_day_key(tz_offset_minutes * 60)
    hourly_acc: Dict[int, List[float]] = defaultdict(lambda: [0.0, 0.0])
    heat: Dict[str, Dict[int, Tuple[float, float]]] = {}
    for s in seats:
        acc = accumulate_by_key(intervals.get(s.id, []), hour_fn)
        heat[str(s.id)] = acc
        for hr, (o, ob) in acc.items():
            hourly_acc[hr][0] += o
            hourly_acc[hr][1] += ob
    hourly = [
        {
            "hour": h,
            "occupancy_pct": round(hourly_acc[h][0] / hourly_acc[h][1] * 100.0, 1) if hourly_acc[h][1] > 0 else None,
            "observed_seat_hours": round(hourly_acc[h][1] / 3600.0, 3),
        }
        for h in range(24)
    ]
    heatmap = {
        "hours": list(range(24)),
        "seats": [
            {
                "seat_id": str(s.id),
                "seat_label": s.label,
                "values": [
                    round(heat[str(s.id)][h][0] / heat[str(s.id)][h][1] * 100.0, 1)
                    if h in heat[str(s.id)] and heat[str(s.id)][h][1] > 0 else None
                    for h in range(24)
                ],
            }
            for s in seats
        ],
    }

    # Startups: measured against the seats actually assigned to them.
    by_startup: Dict[str, Dict[str, Any]] = {}
    for s in seats:
        if not s.startup_id:
            continue
        e = by_startup.setdefault(str(s.startup_id), {"startup_id": str(s.startup_id), "name": s.startup_name, "seat_ids": []})
        e["seat_ids"].append(s.id)
    contracted = {}
    if by_startup:
        contracted = {
            str(sid): n
            for sid, n in (
                await db.execute(select(Startup.id, Startup.allocated_seats).where(Startup.id.in_([UUID(k) for k in by_startup])))
            ).all()
        }
    startup_stats = []
    for key, e in by_startup.items():
        ivs = {sid: intervals.get(sid, []) for sid in e["seat_ids"]}
        tl = bucket_timeline(ivs, s0, s1, bucket_s)
        occ = sum(r["occupied_duration_s"] for r in rows if r["startup_id"] == key)
        obs = sum(r["observed_duration_s"] for r in rows if r["startup_id"] == key)
        assigned = len(e["seat_ids"])
        now_occ = sum(1 for r in rows if r["startup_id"] == key and r["current_status"] == OCCUPIED)
        peak_conc, _ = max_concurrent(ivs)
        at_capacity_s = sum(bucket_s for b in tl if b["observed"] > 0 and b["occupied"] >= assigned - 0.05)
        observed_buckets_s = sum(bucket_s for b in tl if b["observed"] > 0)
        util = round(occ / obs * 100.0, 1) if obs > 0 else None
        startup_stats.append({
            "startup_id": key,
            "name": e["name"],
            "assigned_seats": assigned,
            "contracted_seats": contracted.get(key),
            "occupied_now": now_occ,
            "unused_now": max(0, assigned - now_occ) if any(r["startup_id"] == key and r["current_status"] != UNKNOWN for r in rows) else None,
            "utilization_pct": util,
            "peak_concurrent": round(peak_conc, 2),
            "at_capacity_pct": round(at_capacity_s / observed_buckets_s * 100.0, 1) if observed_buckets_s else None,
            "status": None if util is None else ("UNDER_UTILIZED" if util < 40 else "AT_CAPACITY" if peak_conc >= assigned - 0.05 else "BALANCED"),
        })
    startup_stats.sort(key=lambda r: r["name"] or "")

    under = [r["seat_label"] for r in rows if r["utilization_pct"] is not None and r["utilization_pct"] < 20]
    over = [r["seat_label"] for r in rows if r["utilization_pct"] is not None and r["utilization_pct"] > 85]
    peak_pct = max(observed_pcts) if observed_pcts else None

    timeline = [
        {"time": _iso(b["t"]), "occupancy_pct": b["occupancy_pct"], "occupied": b["occupied"], "observed": b["observed"]}
        for b in timeline_raw
    ]

    return {
        "window": {"since": since.isoformat(), "until": now.isoformat(), "range_hours": range_hours, "bucket_s": bucket_s},
        "sources": {
            "included": ["VIDEO"] + (list(DEMO_SOURCES) if include_demo else []),
            "include_demo": include_demo,
            "video_available": present["video"],
            "demo_available": present["demo"],
        },
        "kpi": {
            "total_seats": len(seats),
            "occupied_seats": occupied_now,
            "vacant_seats": vacant_now,
            "unknown_seats": len(seats) - observed_now,
            "observed_now": observed_now,
            "current_occupancy_pct": round(occupied_now / observed_now * 100.0, 1) if observed_now else None,
            "avg_occupancy_pct": avg_pct,
            "max_occupancy_pct": peak_pct,
            "min_occupancy_pct": min(observed_pcts) if observed_pcts else None,
            "observed_seat_hours": round(total_obs / 3600.0, 2),
            "occupied_seat_hours": round(total_occ / 3600.0, 2),
            "active_startups": len({r["startup_id"] for r in rows if r["startup_id"] and r["current_status"] == OCCUPIED}),
        },
        "timeline": timeline,
        "hourly": hourly,
        "heatmap": heatmap,
        "seat_utilization": [{"seat_label": r["seat_label"], "utilization_pct": r["utilization_pct"]} for r in rows],
        "distribution": {
            "occupied_pct": round(total_occ / total_obs * 100.0, 1) if total_obs else None,
            "vacant_pct": round(100.0 - total_occ / total_obs * 100.0, 1) if total_obs else None,
        },
        "peak": {
            "peak_timestamp": _iso(peak_bucket["t"]) if peak_bucket and peak_bucket["occupied"] > 0 else None,
            "peak_occupied": peak_bucket["occupied"] if peak_bucket else 0,
            "peak_seats": peak_seats,
            "peak_seats_at": _iso(peak_seats_at),
            "highest_occupancy_pct": peak_pct,
            "lowest_occupancy_pct": min(observed_pcts) if observed_pcts else None,
            "avg_occupancy_pct": avg_pct,
            "window": {**window, "start": _iso(window["start"]), "end": _iso(window["end"])} if window else None,
        },
        "capacity": {
            "total_capacity": len(seats),
            "avg_utilization_pct": avg_pct,
            "peak_utilization_pct": peak_pct,
            "unused_capacity_pct": round(100.0 - avg_pct, 1) if avg_pct is not None else None,
            "under_utilized_seats": under,
            "over_utilized_seats": over,
        },
        "seat_stats": rows,
        "startup_stats": startup_stats,
        "performance": await _performance(db, building_id),
    }


async def seat_history(db: AsyncSession, seat_id: UUID, range_hours: float, include_demo: bool) -> Optional[Dict[str, Any]]:
    seat = await db.get(Seat, seat_id)
    if seat is None:
        return None
    zone = await db.get(Zone, seat.zone_id)
    floor = await db.get(Floor, zone.floor_id) if zone else None
    infos = await load_seats(db, floor.building_id, True, include_inactive=True, seat_id=seat_id) if floor else []
    info = infos[0] if infos else None

    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=range_hours)
    ivs = (await load_intervals(db, [seat_id], since, now, include_demo)).get(seat_id, [])
    st = seat_stats(ivs)

    src = _source_filter(include_demo)
    ev_q = (
        select(OccupancyEvent)
        .where(OccupancyEvent.seat_id == seat_id, OccupancyEvent.detected_at >= since)
        .order_by(OccupancyEvent.detected_at.desc())
        .limit(200)
    )
    if src is not None:
        ev_q = ev_q.where(src)
    events = list(reversed((await db.execute(ev_q)).scalars().all()))

    return {
        "seat": {
            "seat_id": str(seat.id),
            "seat_label": seat.seat_label,
            "zone": zone.name if zone else None,
            "floor": floor.name if floor else None,
            "source": seat.source,
            "is_active": seat.is_active,
            "confidence": seat.confidence,
            "bbox": {
                "x": seat.x_coordinate, "y": seat.y_coordinate, "w": seat.width, "h": seat.height,
            },
            "startup_id": str(info.startup_id) if info and info.startup_id else None,
            "startup_name": info.startup_name if info else None,
            "allocation_id": str(info.allocation_id) if info and info.allocation_id else None,
        },
        "window": {"since": since.isoformat(), "until": now.isoformat(), "range_hours": range_hours},
        "stats": {
            **{k: v for k, v in st.items() if k not in ("first_occupied", "last_occupied", "current_since")},
            "first_occupied": _iso(st["first_occupied"]),
            "last_occupied": _iso(st["last_occupied"]),
            "current_since": _iso(st["current_since"]),
            "current_session_s": round(now.timestamp() - st["current_since"], 1)
            if st["current_status"] == OCCUPIED and st["current_since"] else None,
        },
        "intervals": [
            {"start": _iso(i.start), "end": _iso(i.end), "status": i.status, "duration_s": round(i.duration, 1)}
            for i in ivs
        ],
        "events": [
            {
                "at": iso_utc(e.detected_at),
                "status": _status(e.status),
                "video_ts": e.video_ts,
                "session_id": str(e.session_id) if e.session_id else None,
                "source": e.source,
            }
            for e in events
        ],
    }


async def recent_activity(
    db: AsyncSession, building_id: UUID, limit: int, include_demo: bool, range_hours: float = 24
) -> List[Dict[str, Any]]:
    """Recent seat changes (occupied ↔ vacant). Initial observations and run endings are not changes."""
    seats = await load_seats(db, building_id, include_demo, include_inactive=True)
    if not seats:
        return []
    labels = {s.id: s for s in seats}
    since = datetime.now(timezone.utc) - timedelta(hours=range_hours)
    q = (
        select(OccupancyEvent.seat_id, OccupancyEvent.detected_at, OccupancyEvent.status,
               OccupancyEvent.video_ts, OccupancyEvent.source, OccupancyEvent.session_id)
        .where(OccupancyEvent.seat_id.in_(list(labels)), OccupancyEvent.detected_at >= since)
        .order_by(OccupancyEvent.detected_at.desc())
        .limit(max(200, limit * 20))
    )
    src = _source_filter(include_demo)
    if src is not None:
        q = q.where(src)
    rows = list(reversed((await db.execute(q)).all()))
    prev: Dict[UUID, str] = {}
    out: List[Dict[str, Any]] = []
    for sid, dt, st, vts, source, sess in rows:
        status = _status(st)
        p = prev.get(sid)
        prev[sid] = status
        if p is None or status == UNKNOWN or p == UNKNOWN or p == status:
            continue
        s = labels[sid]
        out.append({
            "seat_id": str(sid),
            "label": s.label,
            "zone": s.zone_name,
            "startup_name": s.startup_name,
            "from": p,
            "to": status,
            "at": iso_utc(dt),
            "video_ts": vts,
            "session_id": str(sess) if sess else None,
            "demo": source != EventSource.VIDEO.value,
        })
    return list(reversed(out))[:limit]
