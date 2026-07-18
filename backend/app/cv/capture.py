"""Video capture consumer.

Three modes:
  - "mock": Random occupancy events for DB seats (no CV)
  - "video": Process an uploaded .mp4 file through YOLO pipeline
  - "stream": Process a live RTSP/webcam stream

Architecture for "video" mode:
  1. Open the video file with OpenCV.
  2. Read the first 6 seconds of the video and run ChairDetector to locate all physical chairs
     using spatial IoU clustering and multi-frame voting.
  3. Assign each chair a permanent in-memory SeatDefinition (UUID, label, bbox).
  4. Persist these seats to the SQLite database and broadcast them via WebSocket.
  5. Process every subsequent frame:
     - Run YOLO person pose detection asynchronously in a background thread pool.
     - Compare person bounding boxes against the frozen chair regions to determine occupancy.
     - Draw overlays (predefined boxes, person detections, labels) on EVERY single frame.
     - Encode annotated frame as JPEG and store in self.latest_frame for smooth playback.
  6. Broadcast occupancy updates + stats via WebSocket.
"""
from __future__ import annotations

import asyncio
import cv2
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from app.database import async_session_factory
from app.models.camera import Camera
from app.models.seat import Seat
from app.models.occupancy_event import OccupancyEvent, OccupancyStatus
from app.cv.processor import ChairDetector, SeatOccupancyProcessor, SeatDefinition
from app.api.ws_manager import manager as ws_manager
from app.utils.logger import get_logger

logger = get_logger(__name__)


class VideoCaptureConsumer:
    """Manages the CV pipeline for one camera."""
    def __init__(
        self,
        camera_id: uuid.UUID,
        mode: str = "mock",
        video_path: Optional[str] = None,
        model_path: str = "yolov8n-pose.pt",
    ) -> None:
        self.camera_id = camera_id
        self.mode = mode.lower()
        self.video_path = video_path
        self.model_path = model_path
        self.running = False
        self.task: Optional[asyncio.Task] = None

        # Session tracking
        self.session_id = str(uuid.uuid4())
        self.status = "IDLE"  # "IDLE", "UPLOADING", "PROCESSING", "ANALYZING", "COMPLETED"

        # MJPEG streaming
        self.latest_frame: Optional[bytes] = None

        # Dynamic seat definitions (populated by ChairDetector in video mode)
        # In mock mode, populated from DB seats.
        self.detected_seats: List[SeatDefinition] = []

        # Current occupancy per seat_id
        self.seat_states: Dict[str, str] = {}  # seat_id → "OCCUPIED" | "VACANT"

        # Latest cached CV results (seat_id -> (status, confidence, person_bbox))
        self.latest_results: Dict[str, Tuple[OccupancyStatus, float, Optional[List[float]]]] = {}

    # ─── Lifecycle ──────────────────────────────────────────────────────────

    async def start(self) -> None:
        self.running = True
        self.task = asyncio.create_task(self._run_loop())
        logger.info(f"VideoCaptureConsumer started: camera={self.camera_id} mode={self.mode} session={self.session_id}")

    async def stop(self) -> None:
        self.running = False
        self.status = "IDLE"
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info(f"VideoCaptureConsumer stopped: camera={self.camera_id}")

    async def _run_loop(self) -> None:
        try:
            if self.mode == "mock":
                await self._run_mock()
            else:
                await self._run_cv()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Unhandled exception in VideoCaptureConsumer [{self.camera_id}]: {e}")

    # ─── Mock Mode ──────────────────────────────────────────────────────────

    async def _run_mock(self) -> None:
        """Generate synthetic seat updates using DB seats for the camera's floor/zone."""
        async with async_session_factory() as session:
            camera = await session.get(Camera, self.camera_id)
            if not camera:
                logger.error(f"Camera {self.camera_id} not found")
                return

            if camera.zone_id is not None:
                q = select(Seat).where(Seat.zone_id == camera.zone_id, Seat.is_active.is_(True))
            elif camera.floor_id is not None:
                from app.models.zone import Zone
                q = (
                    select(Seat)
                    .join(Zone, Seat.zone_id == Zone.id)
                    .where(Zone.floor_id == camera.floor_id, Seat.is_active.is_(True))
                )
            else:
                q = select(Seat).where(Seat.is_active.is_(True)).limit(20)

            db_seats = (await session.execute(q)).scalars().all()

        if not db_seats:
            logger.warning(f"No DB seats for mock camera {self.camera_id}")
            return

        # Convert DB seats to SeatDefinitions so the frontend gets a consistent format
        self.detected_seats = [
            SeatDefinition(
                seat_id=str(s.id),
                seat_label=s.seat_label,
                x1=int(s.x_coordinate or 0),
                y1=int(s.y_coordinate or 0),
                x2=int((s.x_coordinate or 0) + (s.width or 80)),
                y2=int((s.y_coordinate or 0) + (s.height or 80)),
                track_id=idx,
            )
            for idx, s in enumerate(db_seats)
        ]
        self.seat_states = {s.seat_id: "VACANT" for s in self.detected_seats}

        # Broadcast initial layout
        await self._broadcast_seat_layout()

        fps = camera.fps or 1
        delay = 1.0 / fps

        while self.running:
            changed = False
            for seat in self.detected_seats:
                if random.random() < 0.05:
                    new_status = "OCCUPIED" if self.seat_states[seat.seat_id] == "VACANT" else "VACANT"
                    self.seat_states[seat.seat_id] = new_status
                    changed = True

                    # Async DB write — catch lock errors gracefully
                    try:
                        async with async_session_factory() as session:
                            event = OccupancyEvent(
                                seat_id=uuid.UUID(seat.seat_id),
                                camera_id=self.camera_id,
                                status=OccupancyStatus(new_status),
                                confidence=random.uniform(0.85, 0.99),
                                detected_at=datetime.now(timezone.utc),
                                person_bbox=None,
                            )
                            session.add(event)
                            await session.commit()
                    except Exception as db_err:
                        logger.debug(f"Mock DB write skipped: {db_err}")

            if changed:
                await self._broadcast_full_matrix()

            await asyncio.sleep(delay)

    # ─── CV Video Mode ───────────────────────────────────────────────────────

    async def _run_cv(self) -> None:
        """
        Process video file through ChairDetector then SeatOccupancyProcessor.

        Phase 1 (chair discovery):
          - Run multi-frame ChairDetector scanning over first 6 seconds of video.
          - Broadcast discovered seat layout to frontend immediately.

        Phase 2 (occupancy loop):
          - For each frame, run YOLO occupancy detection in thread pool on a frozen layout.
          - On every frame, draw overlays using the latest cached coordinates/statuses.
          - Encode annotated frame → JPEG → self.latest_frame.
        """
        source = self.video_path
        if not source:
            logger.error("video_path not set for CV mode")
            return

        import os
        if not os.path.exists(source):
            logger.error(f"Video file not found: {source}")
            return

        loop = asyncio.get_event_loop()

        # ── Phase 1: Chair Discovery ──────────────────────────────────────
        logger.info(f"[{self.camera_id}] Phase 1: Chair detection from first frames of {source}")
        self.status = "PROCESSING"
        await self._broadcast_status()

        # Run chair detection on first 6 seconds of video (CPU-bound)
        chair_detector = ChairDetector(model_path="yolov8n.pt")

        def _on_init_progress(frame_num, total):
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast({
                    "type": "init_progress",
                    "camera_id": str(self.camera_id),
                    "session_id": self.session_id,
                    "frame": frame_num,
                    "total": total,
                    "stage": "Detecting physical seats and building layout map...",
                }),
                loop
            )

        def _detect():
            from app.config import get_settings
            settings = get_settings()
            return chair_detector.detect_chairs_multi_frame(
                source,
                duration_sec=6.0,
                skip=settings.FRAME_SKIP_INTERVAL,
                progress_callback=_on_init_progress,
                is_cancelled=lambda: not self.running
            )

        self.detected_seats = await loop.run_in_executor(None, _detect)

        # Synchronize dynamic seat definitions to database to align REST API and history events
        if self.detected_seats:
            try:
                async with async_session_factory() as session:
                    camera = await session.get(Camera, self.camera_id)
                    if camera and camera.zone_id:
                        from sqlalchemy import delete
                        # Clean up existing seats in this zone
                        await session.execute(delete(Seat).where(Seat.zone_id == camera.zone_id))
                        
                        # Add new detected seats
                        for s in self.detected_seats:
                            db_seat = Seat(
                                id=uuid.UUID(s.seat_id),
                                zone_id=camera.zone_id,
                                seat_label=s.seat_label,
                                x_coordinate=float(s.x1),
                                y_coordinate=float(s.y1),
                                width=float(s.x2 - s.x1),
                                height=float(s.y2 - s.y1),
                                is_active=True
                            )
                            session.add(db_seat)
                        await session.commit()
                        logger.info(f"[{self.camera_id}] Persisted {len(self.detected_seats)} detected seats to database zone {camera.zone_id}.")
            except Exception as db_err:
                logger.error(f"[{self.camera_id}] Failed to persist detected seats: {db_err}")

        # Read first frame of video to initialize streaming frame buffer
        cap_init = cv2.VideoCapture(source)
        ret_init, first_frame = cap_init.read()
        cap_init.release()

        if ret_init:
            _, raw_buf = cv2.imencode(".jpg", first_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            self.latest_frame = raw_buf.tobytes()

        if not self.detected_seats:
            logger.warning(f"[{self.camera_id}] No chairs detected. Seat matrix will be empty.")
        else:
            logger.info(f"[{self.camera_id}] Detected {len(self.detected_seats)} chairs.")

        # Initialize all seats to VACANT
        self.seat_states = {s.seat_id: "VACANT" for s in self.detected_seats}
        self.latest_results = {
            s.seat_id: (OccupancyStatus.VACANT, 0.0, None) for s in self.detected_seats
        }
        
        # Tell frontend the definitive seat layout BEFORE processing starts
        await self._broadcast_seat_layout()
        self.status = "ANALYZING"
        await self._broadcast_status()

        # ── Phase 2: Occupancy Processing Loop ───────────────────────────
        logger.info(f"[{self.camera_id}] Phase 2: Starting occupancy detection loop (Dual-Loop Async)")

        # Create a dedicated ThreadPoolExecutor for running YOLO Pose tracking to avoid event loop contention
        self.inference_executor = ThreadPoolExecutor(max_workers=1)

        occupancy_processor = SeatOccupancyProcessor(model_path=self.model_path)

        def _open_cap():
            cap = cv2.VideoCapture(source)
            video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            return cap, video_fps, total_frames

        cap, video_fps, total_frames = await loop.run_in_executor(None, _open_cap)

        frame_delay = 1.0 / video_fps  # maintain real-time playback speed

        frames_read = 0
        frames_inferred = 0
        infer_start = time.time()

        last_statuses: Dict[str, OccupancyStatus] = {}

        # Loop sharing state
        self.current_frame = None
        self.current_frame_index = 0

        # Background worker for continuous YOLO Pose tracking and seat state transitions
        async def run_inference_worker():
            nonlocal frames_inferred, infer_start
            last_inferred_idx = -1

            while self.running:
                if self.current_frame is not None and self.current_frame_index > last_inferred_idx:
                    frame_to_infer = self.current_frame.copy()
                    current_idx = self.current_frame_index
                    last_inferred_idx = current_idx

                    # Copy seat definitions to prevent thread/concurrency conflicts
                    seats_copy = [
                        SeatDefinition(
                            seat_id=s.seat_id,
                            seat_label=s.seat_label,
                            x1=s.x1,
                            y1=s.y1,
                            x2=s.x2,
                            y2=s.y2,
                            track_id=s.track_id
                        )
                        for s in self.detected_seats
                    ]

                    def _run_bg_inference(f, s_copy):
                        return occupancy_processor.detect_occupancy(f, s_copy)

                    try:
                        # Bypasses the async loop thread blocking using the dedicated single-threaded executor
                        results = await loop.run_in_executor(self.inference_executor, _run_bg_inference, frame_to_infer, seats_copy)
                        self.latest_results = results
                        frames_inferred += 1

                        updated_seats = []
                        any_state_changed = False
                        for seat in self.detected_seats:
                            status, conf, bbox = self.latest_results.get(seat.seat_id, (OccupancyStatus.VACANT, 0.0, None))
                            self.seat_states[seat.seat_id] = status.value
                            updated_seats.append({
                                "seat_id": seat.seat_id,
                                "label": seat.seat_label,
                                "status": status.value,
                            })

                            prev = last_statuses.get(seat.seat_id)
                            if prev != status:
                                last_statuses[seat.seat_id] = status
                                any_state_changed = True
                                asyncio.create_task(self._write_event_to_db(seat, status, conf, bbox))

                        if any_state_changed:
                            current_stage = "Updating Analytics..."
                        elif current_idx % 10 < 3:
                            current_stage = "Tracking People..."
                        elif current_idx % 10 < 6:
                            current_stage = "Detecting Occupancy..."
                        else:
                            current_stage = "Streaming Processed Frames..."

                        await ws_manager.broadcast({
                            "type": "processing_update",
                            "camera_id": str(self.camera_id),
                            "session_id": self.session_id,
                            "frame": current_idx,
                            "total_frames": total_frames,
                            "video_fps": video_fps,
                            "fps": round(frames_inferred / (time.time() - infer_start) if (time.time() - infer_start) > 0 else 0, 1),
                            "seats": updated_seats,
                            "stage": current_stage,
                        })
                    except Exception as e:
                        logger.error(f"Inference worker error: {e}")

                # Target 5 FPS (200ms sleep) for the background tracking task
                await asyncio.sleep(0.20)

        inference_worker_task = asyncio.ensure_future(run_inference_worker())

        try:
            while self.running:
                t0 = time.time()

                # Decode frame synchronously on the main thread to avoid run_in_executor scheduling overhead
                ret, frame = cap.read()
                if not ret:
                    logger.info(f"[{self.camera_id}] Video analysis completed.")
                    self.status = "COMPLETED"
                    self.running = False
                    break

                frames_read += 1
                self.current_frame = frame
                self.current_frame_index = frames_read

                # Draw overlays using latest stable results from the background worker
                annotated = occupancy_processor.draw_overlays(
                    frame,
                    self.detected_seats,
                    self.latest_results,
                )

                # Encode annotated frame to bytes for MJPEG streaming
                _, ann_buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                self.latest_frame = ann_buf.tobytes()

                # Maintain real-time playback speed
                elapsed = time.time() - t0
                sleep_time = frame_delay - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(0)
        finally:
            self.running = False
            if 'inference_worker_task' in locals() and not inference_worker_task.done():
                inference_worker_task.cancel()
                try:
                    await inference_worker_task
                except asyncio.CancelledError:
                    pass

            if hasattr(self, "inference_executor"):
                self.inference_executor.shutdown(wait=False)

            if 'cap' in locals() and cap is not None:
                await loop.run_in_executor(None, cap.release)

            # Clean up temporary uploaded video files to free resources
            if source and os.path.exists(source) and "uploads" in source:
                try:
                    os.remove(source)
                    logger.info(f"[{self.camera_id}] Cleaned up temp video file: {source}")
                except Exception as clean_err:
                    logger.warning(f"[{self.camera_id}] Failed to clean up temp video file {source}: {clean_err}")

            logger.info(f"[{self.camera_id}] CV loops finished.")

    # ─── Helpers ──────────────────────────────────────────────────────────

    async def _broadcast_status(self) -> None:
        """Send the current session status to all connected WebSocket clients."""
        await ws_manager.broadcast({
            "type": "status_update",
            "camera_id": str(self.camera_id),
            "session_id": self.session_id,
            "status": self.status,
        })

    async def _broadcast_seat_layout(self) -> None:
        """Send the definitive seat list to all connected WebSocket clients."""
        await ws_manager.broadcast({
            "type": "seat_layout",
            "camera_id": str(self.camera_id),
            "session_id": self.session_id,
            "seats": [
                {
                    "seat_id": s.seat_id,
                    "label": s.seat_label,
                    "status": self.seat_states.get(s.seat_id, "VACANT"),
                    "bbox": {"x1": s.x1, "y1": s.y1, "x2": s.x2, "y2": s.y2},
                }
                for s in self.detected_seats
            ],
        })

    async def _broadcast_full_matrix(self) -> None:
        """Send current occupancy of all seats."""
        await ws_manager.broadcast({
            "type": "seat_matrix",
            "camera_id": str(self.camera_id),
            "seats": [
                {
                    "seat_id": s.seat_id,
                    "label": s.seat_label,
                    "status": self.seat_states.get(s.seat_id, "VACANT"),
                }
                for s in self.detected_seats
            ],
        })

    async def _write_event_to_db(
        self,
        seat: SeatDefinition,
        status: OccupancyStatus,
        confidence: float,
        bbox: Optional[list],
    ) -> None:
        """Write an occupancy state-change event to the DB. Fire-and-forget."""
        try:
            bbox_dict = None
            if bbox and len(bbox) >= 4:
                bbox_dict = {"x": bbox[0], "y": bbox[1], "w": bbox[2] - bbox[0], "h": bbox[3] - bbox[1]}

            # Only write to DB if the seat_id is a valid UUID (video mode uses new UUIDs)
            try:
                seat_uuid = uuid.UUID(seat.seat_id)
            except ValueError:
                return

            async with async_session_factory() as session:
                # Check if this seat exists in DB; if not, skip (video-mode seats are transient)
                db_seat = await session.get(Seat, seat_uuid)
                if db_seat is None:
                    return

                event = OccupancyEvent(
                    seat_id=seat_uuid,
                    camera_id=self.camera_id,
                    status=status,
                    confidence=confidence,
                    detected_at=datetime.now(timezone.utc),
                    person_bbox=bbox_dict,
                )
                session.add(event)
                await session.commit()
        except Exception as e:
            logger.debug(f"DB write skipped for seat {seat.seat_id}: {e}")


# ─── Camera Manager ────────────────────────────────────────────────────────────

class CameraManager:
    def __init__(self) -> None:
        self.consumers: Dict[uuid.UUID, VideoCaptureConsumer] = {}

    async def start_camera(
        self,
        camera_id: uuid.UUID,
        mode: str = "mock",
        video_path: Optional[str] = None,
    ) -> None:
        await self.stop_camera(camera_id)
        consumer = VideoCaptureConsumer(
            camera_id=camera_id,
            mode=mode,
            video_path=video_path,
        )
        self.consumers[camera_id] = consumer
        await consumer.start()
        logger.info(f"CameraManager: started camera {camera_id} in {mode} mode")

    async def stop_camera(self, camera_id: uuid.UUID) -> None:
        if camera_id in self.consumers:
            await self.consumers[camera_id].stop()
            del self.consumers[camera_id]

    async def start_all(self) -> None:
        async with async_session_factory() as session:
            cameras = (
                await session.execute(select(Camera).where(Camera.is_active.is_(True)))
            ).scalars().all()

        for camera in cameras:
            config = camera.config or {}
            mode = config.get("source_type", "mock")
            video_path = config.get("video_path")

            # Safety: if video file no longer exists, fall back to mock
            if mode == "video" and video_path:
                import os
                if not os.path.exists(video_path):
                    logger.warning(f"Video not found: {video_path} — starting in mock mode")
                    mode = "mock"
                    video_path = None

            await self.start_camera(camera_id=camera.id, mode=mode, video_path=video_path)

    async def stop_all(self) -> None:
        for camera_id in list(self.consumers.keys()):
            await self.stop_camera(camera_id)


# Global singleton
camera_manager = CameraManager()
