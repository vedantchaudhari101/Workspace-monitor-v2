"""Occupancy monitoring API routes."""

from __future__ import annotations

import asyncio
import os
import shutil
import uuid as uuid_module
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import PaginatedResponse
from app.schemas.occupancy import LiveOccupancyResponse, OccupancyEventResponse
from app.services.occupancy_service import OccupancyService
from app.api.ws_manager import manager

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
    source_type: str  # "video" | "mock"
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
    """Update camera source stream or mode (video, mock)."""
    from app.models.camera import Camera
    from app.api.exceptions import NotFoundError

    camera = await db.get(Camera, camera_id)
    if not camera:
        raise NotFoundError("Camera", str(camera_id))

    # Merge into existing config dict (don't overwrite codec/bitrate settings)
    config = dict(camera.config or {})
    config["source_type"] = payload.source_type
    if payload.video_path:
        config["video_path"] = payload.video_path
        camera.stream_url = payload.video_path
    camera.config = config

    await db.flush()
    await db.refresh(camera)

    # Hot-swap the background running camera loop
    from app.cv.capture import camera_manager
    try:
        await camera_manager.start_camera(
            camera_id=camera.id,
            mode=payload.source_type,
            video_path=payload.video_path,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to hot-swap camera stream: {e}")

    return {
        "camera_id": str(camera.id),
        "name": camera.name,
        "source_type": payload.source_type,
        "stream_url": camera.stream_url,
        "config": camera.config,
    }


# ─── Video Upload ──────────────────────────────────────────────────────────────

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
    """Upload a video file, save it locally, and trigger YOLO occupancy processing."""
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    # Use camera_id and uuid to guarantee unique paths, preventing Windows file lock sharing violations
    safe_filename = file.filename.replace("/", "_").replace("\\", "_")
    unique_id = uuid_module.uuid4().hex
    file_path = os.path.join(upload_dir, f"{camera_id}_{unique_id}_{safe_filename}")

    # Write file in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    file_bytes = await file.read()  # read fully into memory

    def _write_file():
        with open(file_path, "wb") as buf:
            buf.write(file_bytes)

    await loop.run_in_executor(None, _write_file)

    from app.models.camera import Camera
    from app.api.exceptions import NotFoundError

    camera = await db.get(Camera, camera_id)
    if not camera:
        raise NotFoundError("Camera", str(camera_id))

    # Merge config — preserve existing codec/bitrate keys
    config = dict(camera.config or {})
    config["source_type"] = "video"
    config["video_path"] = file_path
    camera.config = config
    camera.stream_url = file_path
    await db.flush()

    # Start camera consumer in background — do NOT await the CV loop itself
    from app.cv.capture import camera_manager
    asyncio.create_task(
        camera_manager.start_camera(
            camera_id=camera.id,
            mode="video",
            video_path=file_path,
        )
    )

    return {
        "status": "processing",
        "camera_id": str(camera_id),
        "file_path": file_path,
        "message": "Video uploaded. Chair detection and occupancy analysis started in background.",
    }


# ─── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def occupancy_ws(websocket: WebSocket):
    """WebSocket endpoint for real-time seat occupancy streaming."""
    await manager.connect(websocket)

    # Sync new client with the seat layouts of all active cameras immediately
    from app.cv.capture import camera_manager
    for camera_id, consumer in camera_manager.consumers.items():
        if consumer.detected_seats:
            try:
                await websocket.send_json({
                    "type": "seat_layout",
                    "camera_id": str(camera_id),
                    "seats": [
                        {
                            "seat_id": s.seat_id,
                            "label": s.seat_label,
                            "status": consumer.seat_states.get(s.seat_id, "VACANT"),
                            "bbox": {"x1": s.x1, "y1": s.y1, "x2": s.x2, "y2": s.y2},
                        }
                        for s in consumer.detected_seats
                    ],
                })
            except Exception:
                pass

    try:
        while True:
            # Keep connection alive with a ping/pong; client may send nothing
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send a heartbeat ping to detect dead connections
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
    from app.cv.capture import camera_manager

    if camera_id not in camera_manager.consumers:
        raise HTTPException(status_code=404, detail="Camera stream not found or not running.")

    consumer = camera_manager.consumers[camera_id]

    async def generate_frames():
        import logging
        log = logging.getLogger(__name__)
        last_frame = None
        while True:
            # Check if this consumer is still the active one and running
            if camera_id not in camera_manager.consumers or camera_manager.consumers[camera_id] is not consumer:
                log.info(f"Stream: Consumer for camera {camera_id} was replaced or stopped. Ending old stream.")
                break

            # Check if consumer loop finished
            if not consumer.running and getattr(consumer, "status", None) == "COMPLETED":
                # Send the final frame one last time and exit
                frame_bytes = consumer.latest_frame
                if frame_bytes:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                    )
                log.info(f"Stream: Camera {camera_id} finished processing. Closing stream.")
                break

            frame_bytes = consumer.latest_frame
            # Only send if we have a new frame
            if frame_bytes and frame_bytes is not last_frame:
                last_frame = frame_bytes
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                )
            await asyncio.sleep(0.04)  # 25 fps max yield rate

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ─── Camera Seat State ─────────────────────────────────────────────────────────

@router.get(
    "/camera/{camera_id}/seats",
    summary="Get current seat states for a camera",
)
async def camera_seats(camera_id: UUID):
    """Return current occupancy state of all detected seats for a camera."""
    from app.cv.capture import camera_manager

    if camera_id not in camera_manager.consumers:
        raise HTTPException(status_code=404, detail="Camera not found or not running.")

    consumer = camera_manager.consumers[camera_id]
    seats = [
        {
            "seat_id": s.seat_id,
            "label": s.seat_label,
            "status": consumer.seat_states.get(s.seat_id, "VACANT"),
            "bbox": {"x1": s.x1, "y1": s.y1, "x2": s.x2, "y2": s.y2},
        }
        for s in consumer.detected_seats
    ]
    return {
        "camera_id": str(camera_id),
        "session_id": getattr(consumer, "session_id", None),
        "status": getattr(consumer, "status", "IDLE"),
        "seat_count": len(seats),
        "seats": seats,
    }
