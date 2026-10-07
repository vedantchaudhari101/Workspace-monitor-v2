"""Occupancy monitoring API routes."""

from __future__ import annotations

import asyncio
import os
import shutil
import uuid as uuid_module
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from sqlalchemy import select
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import PaginatedResponse
from app.schemas.occupancy import LiveOccupancyResponse, OccupancyEventResponse
from app.services.occupancy_service import OccupancyService
from app.api.ws_manager import manager
from app.config import get_settings
from app.models.analysis_session import AnalysisSession, SessionStatus
from app.models.camera import Camera
from app.api.exceptions import NotFoundError
from app.utils.timefmt import iso_utc

router = APIRouter()


# ─── Live Occupancy ────────────────────────────────────────────────────────────

@router.get(
    "/live/{building_id}",
    response_model=LiveOccupancyResponse,
    summary="Live seat occupancy",
)
async def live_occupancy(
    building_id: UUID,
    db: DbSession,
    _user: CurrentUser,
) -> LiveOccupancyResponse:
    """Return real-time seat occupancy for every seat in a building."""
    return await OccupancyService(db).get_live_occupancy(building_id)


# ─── Event History ─────────────────────────────────────────────────────────────

@router.get(
    "/events",
    response_model=PaginatedResponse[OccupancyEventResponse],
    summary="Occupancy event history",
)
async def list_events(
    db: DbSession,
    _user: CurrentUser,
    building_id: UUID | None = Query(default=None),
    seat_id: UUID | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedResponse[OccupancyEventResponse]:
    """Return paginated historical occupancy detection events."""
    return await OccupancyService(db).list_events(
        building_id=building_id,
        seat_id=seat_id,
        since=since,
        until=until,
        page=page,
        page_size=page_size,
    )


# ─── Camera Source Control ─────────────────────────────────────────────────────

class CameraSourceUpdate(BaseModel):
    source_type: str  # "video" | "mock" | "idle"
    video_path: str | None = None


@router.post(
    "/camera/{camera_id}/source",
    summary="Update camera source",
)
async def update_camera_source(
    camera_id: UUID,
    payload: CameraSourceUpdate,
    db: DbSession,
    _user: CurrentUser,
):
    """Switch a camera between idle, demo simulation (DEMO_MODE only) and a server-side video."""
    camera = await db.get(Camera, camera_id)
    if not camera:
        raise NotFoundError("Camera", str(camera_id))
    if payload.source_type == "mock" and not get_settings().DEMO_MODE:
        raise HTTPException(status_code=400, detail="Simulated (mock) mode is only available when DEMO_MODE is enabled.")
    if payload.source_type not in ("video", "mock", "idle"):
        raise HTTPException(status_code=400, detail="source_type must be 'video', 'mock' or 'idle'.")

    config = dict(camera.config or {})
    config["source_type"] = payload.source_type
    if payload.video_path:
        config["video_path"] = payload.video_path
        camera.stream_url = payload.video_path
    camera.config = config
    await db.flush()
    await db.commit()

    from app.cv.capture import camera_manager

    if payload.source_type == "idle":
        await camera_manager.stop_camera(camera.id)
    else:
        session_id = None
        if payload.source_type == "video":
            if not payload.video_path:
                raise HTTPException(status_code=400, detail="video_path is required for video mode.")
            row = AnalysisSession(
                camera_id=camera.id,
                source_filename=os.path.basename(payload.video_path),
                mode="video",
                pipeline=get_settings().CV_PIPELINE,
                status=SessionStatus.UPLOADED.value,
            )
            db.add(row)
            await db.commit()
            session_id = row.id
        await camera_manager.start_camera(
            camera_id=camera.id,
            mode=payload.source_type,
            video_path=payload.video_path,
            session_db_id=session_id,
            source_filename=os.path.basename(payload.video_path) if payload.video_path else None,
        )

    return {
        "camera_id": str(camera.id),
        "name": camera.name,
        "source_type": payload.source_type,
        "stream_url": camera.stream_url,
        "config": camera.config,
    }


# ─── Video Upload ──────────────────────────────────────────────────────────────

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
CHUNK = 1024 * 1024


@router.post(
    "/camera/{camera_id}/upload-video",
    summary="Upload and process video for occupancy analysis",
)
async def upload_and_process_video(
    camera_id: UUID,
    db: DbSession,
    _user: CurrentUser,
    file: UploadFile = File(...),
):
    """Stream a video to disk, validate it, open an analysis session and start the pipeline."""
    settings = get_settings()
    camera = await db.get(Camera, camera_id)
    if not camera:
        raise NotFoundError("Camera", str(camera_id))

    original = os.path.basename(file.filename or "video.mp4")
    ext = os.path.splitext(original)[1].lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext or 'none'}'. Use one of: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}.",
        )

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in original)
    file_path = os.path.join(settings.UPLOAD_DIR, f"{camera_id}_{uuid_module.uuid4().hex}_{safe_name}")
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    loop = asyncio.get_running_loop()

    out = await loop.run_in_executor(None, open, file_path, "wb")
    try:
        while True:
            chunk = await file.read(CHUNK)
            if not chunk:
                break
            written += len(chunk)
            if written > limit:
                raise HTTPException(status_code=413, detail=f"Video is larger than the {settings.MAX_UPLOAD_MB} MB limit.")
            await loop.run_in_executor(None, out.write, chunk)
    except HTTPException:
        out.close()
        os.remove(file_path)
        raise
    finally:
        if not out.closed:
            out.close()

    def _probe():
        import cv2

        cap = cv2.VideoCapture(file_path)
        ok = cap.isOpened()
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) if ok else 0
        cap.release()
        return ok and frames > 0

    if not await loop.run_in_executor(None, _probe):
        os.remove(file_path)
        raise HTTPException(status_code=422, detail="The file could not be read as a video. Try re-exporting it as H.264 MP4.")

    session_row = AnalysisSession(
        camera_id=camera.id,
        source_filename=original,
        mode="video",
        pipeline=settings.CV_PIPELINE,
        status=SessionStatus.UPLOADED.value,
    )
    db.add(session_row)
    config = dict(camera.config or {})
    config["source_type"] = "video"
    config["video_path"] = file_path
    camera.config = config
    camera.stream_url = file_path
    await db.commit()

    from app.cv.capture import camera_manager

    asyncio.create_task(
        camera_manager.start_camera(
            camera_id=camera.id,
            mode="video",
            video_path=file_path,
            session_db_id=session_row.id,
            source_filename=original,
        )
    )

    return {
        "status": "processing",
        "camera_id": str(camera_id),
        "session_id": str(session_row.id),
        "file_name": original,
        "size_bytes": written,
        "message": "Video uploaded. Seat calibration and occupancy analysis started.",
    }


@router.post("/camera/{camera_id}/stop", summary="Stop the running analysis for a camera")
async def stop_camera_analysis(camera_id: UUID, _user: CurrentUser):
    """Stop processing; the session is finalised with the data observed so far."""
    from app.cv.capture import camera_manager

    consumer = camera_manager.consumers.get(camera_id)
    if consumer is None or not consumer.running:
        raise HTTPException(status_code=409, detail="Nothing is running on this camera.")
    await camera_manager.stop_camera(camera_id)
    return {"camera_id": str(camera_id), "status": consumer.status}


# ─── Camera state & sessions ───────────────────────────────────────────────────

def _session_brief(row: AnalysisSession) -> dict:
    summary = row.summary or {}
    return {
        "id": str(row.id),
        "camera_id": str(row.camera_id),
        "source_filename": row.source_filename,
        "mode": row.mode,
        "pipeline": row.pipeline,
        "status": row.status,
        "created_at": iso_utc(row.created_at),
        "started_at": iso_utc(row.started_at),
        "completed_at": iso_utc(row.completed_at),
        "video_duration_s": row.video_duration_s,
        "frame_w": row.frame_w,
        "frame_h": row.frame_h,
        "seat_count": row.seat_count,
        "frames_processed": row.frames_processed,
        "frames_inferred": row.frames_inferred,
        "avg_inference_ms": row.avg_inference_ms,
        "calibration_s": row.calibration_s,
        "peak_occupied": summary.get("peak_occupied"),
        "avg_occupancy_pct": summary.get("avg_occupancy_pct"),
        "error": row.error,
    }


@router.get("/camera/{camera_id}/state", summary="Current pipeline state for a camera")
async def camera_state(camera_id: UUID, db: DbSession, _user: CurrentUser):
    """Live state when a run is active or finished in this process; otherwise the last stored session."""
    from app.cv.capture import camera_manager

    camera = await db.get(Camera, camera_id)
    if not camera:
        raise NotFoundError("Camera", str(camera_id))
    consumer = camera_manager.consumers.get(camera_id)
    if consumer is not None:
        return {"live": True, **consumer.snapshot()}

    last = (
        await db.execute(
            select(AnalysisSession)
            .where(AnalysisSession.camera_id == camera_id)
            .order_by(AnalysisSession.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return {
        "live": False,
        "camera_id": str(camera_id),
        "status": "IDLE",
        "stage": "IDLE",
        "demo": False,
        "seats": [],
        "last_session": _session_brief(last) if last else None,
    }


@router.get("/sessions", summary="List analysis sessions")
async def list_sessions(
    db: DbSession,
    _user: CurrentUser,
    camera_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Most recent analysis sessions, newest first."""
    q = select(AnalysisSession).order_by(AnalysisSession.created_at.desc()).limit(limit)
    if camera_id:
        q = q.where(AnalysisSession.camera_id == camera_id)
    rows = (await db.execute(q)).scalars().all()
    return [_session_brief(r) for r in rows]


@router.get("/sessions/{session_id}", summary="Analysis session detail")
async def get_session(session_id: UUID, db: DbSession, _user: CurrentUser):
    """Session metadata plus the stored post-analysis summary."""
    row = await db.get(AnalysisSession, session_id)
    if not row:
        raise NotFoundError("AnalysisSession", str(session_id))
    return {**_session_brief(row), "summary": row.summary}


@router.get("/camera/{camera_id}/summary", summary="Latest completed session summary for a camera")
async def camera_summary(camera_id: UUID, db: DbSession, _user: CurrentUser):
    row = (
        await db.execute(
            select(AnalysisSession)
            .where(AnalysisSession.camera_id == camera_id, AnalysisSession.summary.isnot(None))
            .order_by(AnalysisSession.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No analysed sessions for this camera yet.")
    return {**_session_brief(row), "summary": row.summary}


# ─── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def occupancy_ws(websocket: WebSocket):
    """WebSocket endpoint for real-time seat occupancy streaming."""
    await manager.connect(websocket)

    from app.cv.capture import camera_manager

    for camera_id, consumer in list(camera_manager.consumers.items()):
        try:
            await websocket.send_json({"type": "state_sync", **consumer.snapshot()})
            if consumer.detected_seats:
                await websocket.send_json({
                    "type": "seat_layout",
                    "camera_id": str(camera_id),
                    "session_id": consumer.session_id,
                    "frame_w": consumer.frame_w,
                    "frame_h": consumer.frame_h,
                    "demo": consumer.mode == "mock",
                    "seats": consumer.seat_payload(),
                })
        except Exception:
            pass

    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# ─── MJPEG Video Stream ────────────────────────────────────────────────────────

@router.get(
    "/camera/{camera_id}/stream",
    summary="Live MJPEG video stream from camera capture loop",
)
async def camera_stream(camera_id: UUID):
    """
    Stream MJPEG annotated frames from the camera's capture loop.
    No authentication required so the browser <img> tag can render it directly.
    """
    from app.cv.capture import camera_manager, TERMINAL_STATUSES

    consumer = camera_manager.consumers.get(camera_id)
    if consumer is None or consumer.mode == "mock":
        raise HTTPException(status_code=404, detail="Camera stream not found or not running.")

    async def generate_frames():
        last_frame = None
        while True:
            if camera_manager.consumers.get(camera_id) is not consumer:
                break
            if not consumer.running and consumer.status in TERMINAL_STATUSES:
                if consumer.latest_frame:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + consumer.latest_frame + b"\r\n"
                break
            frame_bytes = consumer.latest_frame
            if frame_bytes and frame_bytes is not last_frame:
                last_frame = frame_bytes
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            await asyncio.sleep(0.04)

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"},
    )


@router.get("/camera/{camera_id}/frame", summary="Latest annotated frame as JPEG")
async def camera_frame(camera_id: UUID):
    """Single JPEG — used to show the final frame after a run has finished."""
    from fastapi import Response
    from app.cv.capture import camera_manager

    consumer = camera_manager.consumers.get(camera_id)
    if consumer is None or not consumer.latest_frame:
        raise HTTPException(status_code=404, detail="No frame available.")
    return Response(content=consumer.latest_frame, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


# ─── Camera Seat State (kept for compatibility) ────────────────────────────────

@router.get(
    "/camera/{camera_id}/seats",
    summary="Get current seat states for a camera",
)
async def camera_seats(camera_id: UUID):
    """Return current occupancy state of all detected seats for a camera."""
    from app.cv.capture import camera_manager

    consumer = camera_manager.consumers.get(camera_id)
    if consumer is None:
        raise HTTPException(status_code=404, detail="Camera not found or not running.")
    seats = consumer.seat_payload()
    return {
        "camera_id": str(camera_id),
        "session_id": consumer.session_id,
        "status": consumer.status,
        "seat_count": len(seats),
        "seats": seats,
    }
