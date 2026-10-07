"""Video capture consumer — runs the CV pipeline for one camera.

Modes:
  - "video": process an uploaded video through the YOLO pipeline (real data)
  - "mock":  random seat toggles for seeded seats. Only started when
             ``DEMO_MODE`` is on; every event it writes is tagged ``MOCK``.

Video mode, end to end:
  1. Probe the file and mark the analysis session CALIBRATING.
  2. Phase 1 — calibrate the seat layout (report pipeline by default).
  3. Match detected seats to the seats this camera found before (E1), so
     seat identity, history and company allocation survive a re-upload.
  4. Phase 2 — a playback loop paced at the video's own frame rate draws
     overlays and serves MJPEG frames, while an inference loop (~5 Hz)
     updates seat state machines.
  5. Every state change is written to ``occupancy_events`` (with session id,
     source=VIDEO and video timestamp) through a single batched writer, and
     broadcast over WebSocket as ``seat_transition``.
  6. When the run ends (completed, stopped or failed) each seat gets a closing
     UNKNOWN event so analytics never extend an observation past the video,
     and a summary is computed and stored on the session.
"""
from __future__ import annotations

import asyncio
import os
import random
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Tuple

from sqlalchemy import select

from app.analytics.session_summary import compute_session_summary
from app.api.ws_manager import manager as ws_manager
from app.config import get_settings
from app.database import async_session_factory
from app.models.analysis_session import AnalysisSession, SessionStatus
from app.models.camera import Camera
from app.models.occupancy_event import EventSource, OccupancyEvent, OccupancyStatus
from app.models.seat import Seat
from app.cv.processor import SeatDefinition, iou
from app.utils.logger import get_logger

logger = get_logger(__name__)

TERMINAL_STATUSES = ("COMPLETED", "STOPPED", "FAILED")
STREAM_MAX_WIDTH = 1280  # MJPEG frames are downscaled for bandwidth; seat boxes use source pixels


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _label_number(label: str) -> int:
    digits = "".join(ch for ch in label if ch.isdigit())
    return int(digits) if digits else 0


class VideoCaptureConsumer:
    """Manages the CV pipeline for one camera."""

    def __init__(
        self,
        camera_id: uuid.UUID,
        mode: str = "mock",
        video_path: Optional[str] = None,
        session_db_id: Optional[uuid.UUID] = None,
        source_filename: Optional[str] = None,
        model_path: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.camera_id = camera_id
        self.mode = mode.lower()
        self.video_path = video_path
        self.source_filename = source_filename
        self.model_path = model_path or settings.POSE_MODEL_PATH
        self.pipeline = settings.CV_PIPELINE if settings.CV_PIPELINE in ("report", "legacy") else "report"
        self.running = False
        self.task: Optional[asyncio.Task] = None

        self.session_db_id = session_db_id
        self.session_id = str(session_db_id) if session_db_id else str(uuid.uuid4())
        self.status = "IDLE"   # IDLE | PROCESSING | ANALYZING | COMPLETED | STOPPED | FAILED | SIMULATING
        self.stage = "IDLE"    # IDLE | CALIBRATING | TRACKING | FINALIZING | DONE | SIMULATING

        self.latest_frame: Optional[bytes] = None
        self.detected_seats: List[SeatDefinition] = []
        self.seat_states: Dict[str, str] = {}
        self.latest_results: Dict[str, Tuple[OccupancyStatus, float, Optional[List[float]]]] = {}

        # Real throughput / progress metrics
        self.frame_w: Optional[int] = None
        self.frame_h: Optional[int] = None
        self.video_fps: Optional[float] = None
        self.total_frames = 0
        self.current_frame_index = 0
        self.frames_inferred = 0
        self.inference_ms: Optional[float] = None
        self.tracking_started: Optional[float] = None
        self.calibration_progress: Tuple[int, int] = (0, 0)
        self.calibration_meta: Optional[Dict[str, Any]] = None
        self.started_at: Optional[datetime] = None

        # Session record keeping
        self.recent_transitions: Deque[Dict[str, Any]] = deque(maxlen=100)
        self.samples: List[Tuple[float, int]] = []
        self.session_transitions: List[Tuple[str, str, float]] = []
        self.summary: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None

        self._events: "asyncio.Queue[Optional[Dict[str, Any]]]" = asyncio.Queue()
        self._writer_task: Optional[asyncio.Task] = None
        self._stop_requested = False

    # ─── Lifecycle ──────────────────────────────────────────────────────────

    async def start(self) -> None:
        self.running = True
        self.task = asyncio.create_task(self._run_loop())
        logger.info(f"VideoCaptureConsumer started: camera={self.camera_id} mode={self.mode} session={self.session_id}")

    async def stop(self, timeout: float = 30.0) -> None:
        """Ask the loops to finish, then wait for the run to finalise."""
        self._stop_requested = True
        self.running = False
        if self.task and not self.task.done():
            try:
                await asyncio.wait_for(asyncio.shield(self.task), timeout=timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self.task.cancel()
                try:
                    await self.task
                except (asyncio.CancelledError, Exception):
                    pass
        logger.info(f"VideoCaptureConsumer stopped: camera={self.camera_id}")

    async def _run_loop(self) -> None:
        self._writer_task = asyncio.create_task(self._event_writer())
        try:
            if self.mode == "mock":
                await self._run_mock()
            else:
                await self._run_cv()
        except asyncio.CancelledError:
            pass
        except Exception as e:  # pragma: no cover — logged for operators
            logger.exception(f"Unhandled exception in VideoCaptureConsumer [{self.camera_id}]: {e}")
        finally:
            await self._events.put(None)
            if self._writer_task:
                try:
                    await asyncio.wait_for(self._writer_task, timeout=15)
                except Exception:
                    pass

    # ─── Snapshot for REST / WS sync ─────────────────────────────────────────

    def seat_payload(self) -> List[Dict[str, Any]]:
        return [
            {
                "seat_id": s.seat_id,
                "label": s.seat_label,
                "status": self.seat_states.get(s.seat_id, "VACANT"),
                "bbox": {"x1": s.x1, "y1": s.y1, "x2": s.x2, "y2": s.y2},
                "confidence": s.confidence,
            }
            for s in self.detected_seats
        ]

    def inference_fps(self) -> float:
        if not self.tracking_started or self.frames_inferred == 0:
            return 0.0
        elapsed = time.time() - self.tracking_started
        return round(self.frames_inferred / elapsed, 2) if elapsed > 0 else 0.0

    def snapshot(self) -> Dict[str, Any]:
        cal_frame, cal_total = self.calibration_progress
        return {
            "camera_id": str(self.camera_id),
            "session_id": self.session_id,
            "mode": self.mode,
            "demo": self.mode == "mock",
            "status": self.status,
            "stage": self.stage,
            "pipeline": self.pipeline,
            "source_filename": self.source_filename,
            "frame_w": self.frame_w,
            "frame_h": self.frame_h,
            "video_fps": self.video_fps,
            "total_frames": self.total_frames,
            "frame": self.current_frame_index,
            "frames_inferred": self.frames_inferred,
            "fps": self.inference_fps(),
            "inference_ms": round(self.inference_ms, 1) if self.inference_ms else None,
            "calibration": {"frame": cal_frame, "total": cal_total, "meta": self.calibration_meta},
            "seats": self.seat_payload(),
            "recent_transitions": list(self.recent_transitions),
            "summary": self.summary,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }

    # ─── Mock Mode (demo only) ─────────────────────────────────────────────

    async def _run_mock(self) -> None:
        """Synthetic seat toggles for seeded seats. Everything is tagged MOCK."""
        async with async_session_factory() as session:
            camera = await session.get(Camera, self.camera_id)
            if not camera:
                logger.error(f"Camera {self.camera_id} not found")
                return
            from app.models.zone import Zone

            if camera.zone_id is not None:
                q = select(Seat).where(Seat.zone_id == camera.zone_id, Seat.is_active.is_(True))
            elif camera.floor_id is not None:
                q = (
                    select(Seat)
                    .join(Zone, Seat.zone_id == Zone.id)
                    .where(Zone.floor_id == camera.floor_id, Seat.is_active.is_(True))
                )
            else:
                q = select(Seat).where(Seat.is_active.is_(True)).limit(20)
            db_seats = (await session.execute(q)).scalars().all()
            fps = camera.fps or 1

        if not db_seats:
            logger.warning(f"No DB seats for mock camera {self.camera_id}")
            return

        self.status = "SIMULATING"
        self.stage = "SIMULATING"
        self.detected_seats = [
            SeatDefinition(
                seat_id=str(s.id),
                seat_label=s.seat_label,
                x1=int(s.x_coordinate or 0),
                y1=int(s.y_coordinate or 0),
                x2=int((s.x_coordinate or 0) + (s.width or 80)),
                y2=int((s.y_coordinate or 0) + (s.height or 80)),
            )
            for s in db_seats
        ]
        self.frame_w = max(s.x2 for s in self.detected_seats) + 40
        self.frame_h = max(s.y2 for s in self.detected_seats) + 40
        self.seat_states = {s.seat_id: "VACANT" for s in self.detected_seats}
        await self._broadcast_seat_layout()
        await self._broadcast_status()

        delay = 1.0 / fps
        while self.running:
            changed = False
            for seat in self.detected_seats:
                if random.random() < 0.05:
                    prev = self.seat_states[seat.seat_id]
                    new_status = "OCCUPIED" if prev == "VACANT" else "VACANT"
                    self.seat_states[seat.seat_id] = new_status
                    changed = True
                    await self._record_transition(seat, prev, new_status, None, random.uniform(0.85, 0.99), None, EventSource.MOCK)
            if changed:
                await self._broadcast_full_matrix()
            await asyncio.sleep(delay)

    # ─── CV Video Mode ─────────────────────────────────────────────────────

    async def _run_cv(self) -> None:
        import cv2

        settings = get_settings()
        source = self.video_path
        if not source or not os.path.exists(source):
            self.error = "The uploaded video could not be found on the server."
            await self._finalize("FAILED", 0)
            return

        loop = asyncio.get_running_loop()
        self.started_at = _now()
        self.status = "PROCESSING"
        self.stage = "CALIBRATING"

        def _probe():
            cap = cv2.VideoCapture(source)
            meta = (
                cap.get(cv2.CAP_PROP_FPS) or 25.0,
                int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
                int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
                int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
            )
            cap.release()
            return meta

        self.video_fps, self.total_frames, self.frame_w, self.frame_h = await loop.run_in_executor(None, _probe)
        await self._update_session(
            status=SessionStatus.CALIBRATING.value,
            started_at=self.started_at,
            pipeline=self.pipeline,
            video_fps=self.video_fps,
            total_frames=self.total_frames,
            video_duration_s=round(self.total_frames / self.video_fps, 2) if self.video_fps else None,
            frame_w=self.frame_w,
            frame_h=self.frame_h,
        )
        await self._broadcast_status()

        frames_read = 0
        final_status = "COMPLETED"
        try:
            # ── Phase 1: calibration ────────────────────────────────────────
            cal_started = time.time()
            last_progress = [0.0]

            def _on_progress(frame_num: int, total: int) -> None:
                self.calibration_progress = (frame_num, total)
                now = time.time()
                if now - last_progress[0] < 0.25 and frame_num < total:
                    return
                last_progress[0] = now
                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast({
                        "type": "init_progress",
                        "camera_id": str(self.camera_id),
                        "session_id": self.session_id,
                        "frame": frame_num,
                        "total": total,
                        "stage": "CALIBRATING",
                    }),
                    loop,
                )

            def _calibrate():
                from app.cv.processor import ChairDetector

                detector = ChairDetector(model_path=settings.YOLO_MODEL_PATH)
                if self.pipeline == "legacy":
                    seats = detector.detect_chairs_multi_frame(
                        source,
                        duration_sec=6.0,
                        skip=settings.FRAME_SKIP_INTERVAL,
                        progress_callback=_on_progress,
                        is_cancelled=lambda: not self.running,
                    )
                    return seats, {"pipeline": "legacy", "seats": len(seats)}
                return detector.calibrate(
                    source,
                    max_frames=settings.CALIBRATION_FRAMES,
                    skip=settings.CALIBRATION_SKIP,
                    progress_callback=_on_progress,
                    is_cancelled=lambda: not self.running,
                )

            seats, meta = await loop.run_in_executor(None, _calibrate)
            self.calibration_meta = meta
            if not self.running:
                final_status = "STOPPED"
                return

            self.detected_seats = await self._sync_seats(seats)
            self.seat_states = {s.seat_id: "VACANT" for s in self.detected_seats}
            self.latest_results = {s.seat_id: (OccupancyStatus.VACANT, 0.0, None) for s in self.detected_seats}
            await self._update_session(
                seat_count=len(self.detected_seats),
                calibration_s=round(time.time() - cal_started, 2),
            )
            if not self.detected_seats:
                logger.warning(f"[{self.camera_id}] No chairs detected. Seat matrix will be empty.")

            def _first_frame():
                cap = cv2.VideoCapture(source)
                ok, frame = cap.read()
                cap.release()
                if not ok:
                    return None
                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                return buf.tobytes()

            self.latest_frame = await loop.run_in_executor(None, _first_frame)
            await self._broadcast_seat_layout()

            # ── Phase 2: occupancy tracking ──────────────────────────────────
            self.status = "ANALYZING"
            self.stage = "TRACKING"
            await self._update_session(status=SessionStatus.TRACKING.value)
            await self._broadcast_status()

            def _make_processor():
                from app.cv.processor import SeatOccupancyProcessor

                return SeatOccupancyProcessor(
                    model_path=self.model_path,
                    pipeline=self.pipeline,
                    occ_frames=settings.OCC_FRAMES,
                    clear_frames=settings.CLEAR_FRAMES,
                    velocity_gate_px=settings.VELOCITY_GATE_PX,
                    hip_weight=settings.HIP_WEIGHT,
                    cross_expand=settings.CROSS_EXPAND,
                )

            processor = await loop.run_in_executor(None, _make_processor)
            inference_executor = ThreadPoolExecutor(max_workers=1)

            cap = await loop.run_in_executor(None, cv2.VideoCapture, source)
            fps = self.video_fps or 25.0
            frame_delay = 1.0 / fps
            current = {"frame": None, "idx": 0}
            last_statuses: Dict[str, OccupancyStatus] = {}
            self.tracking_started = time.time()

            async def inference_worker():
                last_idx = -1
                while self.running:
                    t_start = time.time()
                    if current["frame"] is not None and current["idx"] > last_idx:
                        frame = current["frame"].copy()
                        idx = current["idx"]
                        last_idx = idx
                        seats_copy = list(self.detected_seats)
                        try:
                            results = await loop.run_in_executor(
                                inference_executor, processor.detect_occupancy, frame, seats_copy
                            )
                        except Exception as e:
                            logger.error(f"Inference worker error: {e}")
                            await asyncio.sleep(0.2)
                            continue
                        elapsed_ms = (time.time() - t_start) * 1000.0
                        self.inference_ms = elapsed_ms if self.inference_ms is None else 0.8 * self.inference_ms + 0.2 * elapsed_ms
                        self.latest_results = results
                        self.frames_inferred += 1
                        ts = idx / fps

                        occupied = 0
                        payload = []
                        for seat in self.detected_seats:
                            status, conf, bbox = results.get(seat.seat_id, (OccupancyStatus.VACANT, 0.0, None))
                            if status == OccupancyStatus.OCCUPIED:
                                occupied += 1
                            prev = last_statuses.get(seat.seat_id)
                            if prev != status:
                                last_statuses[seat.seat_id] = status
                                self.seat_states[seat.seat_id] = status.value
                                await self._record_transition(
                                    seat,
                                    prev.value if prev else None,
                                    status.value,
                                    ts,
                                    conf,
                                    bbox,
                                    EventSource.VIDEO,
                                )
                            payload.append({"seat_id": seat.seat_id, "label": seat.seat_label, "status": status.value})
                        self.samples.append((ts, occupied))

                        await ws_manager.broadcast({
                            "type": "processing_update",
                            "camera_id": str(self.camera_id),
                            "session_id": self.session_id,
                            "stage": "TRACKING",
                            "frame": idx,
                            "total_frames": self.total_frames,
                            "video_fps": fps,
                            "video_ts": round(ts, 2),
                            "fps": self.inference_fps(),
                            "inference_ms": round(self.inference_ms, 1) if self.inference_ms else None,
                            "occupied": occupied,
                            "seats": payload,
                        })
                    await asyncio.sleep(max(0.01, 0.20 - (time.time() - t_start)))

            worker = asyncio.ensure_future(inference_worker())
            try:
                while self.running:
                    t0 = time.time()
                    ret, frame = cap.read()
                    if not ret:
                        logger.info(f"[{self.camera_id}] Video analysis completed.")
                        break
                    frames_read += 1
                    self.current_frame_index = frames_read
                    current["frame"] = frame
                    current["idx"] = frames_read
                    annotated = processor.draw_overlays(frame.copy(), self.detected_seats, self.latest_results)
                    if annotated.shape[1] > STREAM_MAX_WIDTH:
                        scale = STREAM_MAX_WIDTH / annotated.shape[1]
                        annotated = cv2.resize(
                            annotated, (STREAM_MAX_WIDTH, int(annotated.shape[0] * scale)), interpolation=cv2.INTER_AREA
                        )
                    _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    self.latest_frame = buf.tobytes()
                    sleep_time = frame_delay - (time.time() - t0)
                    await asyncio.sleep(sleep_time if sleep_time > 0 else 0)
                if self._stop_requested:
                    final_status = "STOPPED"
            finally:
                self.running = False
                if not worker.done():
                    worker.cancel()
                    try:
                        await worker
                    except (asyncio.CancelledError, Exception):
                        pass
                inference_executor.shutdown(wait=False)
                await loop.run_in_executor(None, cap.release)
        except asyncio.CancelledError:
            final_status = "STOPPED"
        except Exception as e:
            logger.exception(f"[{self.camera_id}] CV pipeline failed: {e}")
            self.error = f"{type(e).__name__}: {e}"
            final_status = "FAILED"
        finally:
            self.running = False
            await self._finalize(final_status, frames_read)
            if source and os.path.exists(source) and get_settings().UPLOAD_DIR in source:
                try:
                    os.remove(source)
                except Exception as clean_err:
                    logger.warning(f"[{self.camera_id}] Failed to clean up temp video file {source}: {clean_err}")
            logger.info(f"[{self.camera_id}] CV loops finished with status {final_status}.")

    async def _finalize(self, final_status: str, frames_read: int) -> None:
        """Close the observation window, compute the summary and persist the session."""
        self.stage = "FINALIZING"
        fps = self.video_fps or 25.0
        end_ts = frames_read / fps if frames_read else 0.0

        # Closing UNKNOWN events: the system no longer knows these seats' state.
        for seat in self.detected_seats:
            if self.seat_states.get(seat.seat_id) is not None and any(
                t[0] == seat.seat_id for t in self.session_transitions
            ):
                await self._events.put(self._event_row(seat, OccupancyStatus.UNKNOWN.value, end_ts, None, None, EventSource.VIDEO))

        summary = None
        if self.detected_seats or self.calibration_meta:
            summary = compute_session_summary(
                [{"seat_id": s.seat_id, "label": s.seat_label} for s in self.detected_seats],
                self.session_transitions,
                self.samples,
                end_ts,
            )
            summary["calibration"] = self.calibration_meta
            summary["performance"] = {
                "frames_processed": frames_read,
                "frames_inferred": self.frames_inferred,
                "avg_inference_ms": round(self.inference_ms, 1) if self.inference_ms else None,
                "inference_fps": self.inference_fps(),
                "video_fps": self.video_fps,
                "processing_s": round((_now() - self.started_at).total_seconds(), 1) if self.started_at else None,
            }
        self.summary = summary
        self.status = final_status
        self.stage = "DONE"

        db_status = {
            "COMPLETED": SessionStatus.COMPLETED.value,
            "STOPPED": SessionStatus.STOPPED.value,
            "FAILED": SessionStatus.FAILED.value,
        }[final_status]
        await self._update_session(
            status=db_status,
            completed_at=_now(),
            frames_processed=frames_read,
            frames_inferred=self.frames_inferred,
            avg_inference_ms=round(self.inference_ms, 1) if self.inference_ms else None,
            summary=summary,
            error=self.error,
        )
        await ws_manager.broadcast({
            "type": "session_summary",
            "camera_id": str(self.camera_id),
            "session_id": self.session_id,
            "status": final_status,
            "summary": summary,
            "error": self.error,
        })
        await self._broadcast_status()

    # ─── Seat identity (E1) ──────────────────────────────────────────────────

    async def _sync_seats(self, detected: List[SeatDefinition]) -> List[SeatDefinition]:
        """Match fresh detections to this camera's known seats instead of deleting them.

        * a detection overlapping a known detected seat (IoU >= SEAT_MATCH_IOU)
          keeps that seat's id and label — history and allocations carry over;
        * new detections become new seats with the next free label;
        * known seats that were not seen again are deactivated, not deleted.
        """
        from app.services.bootstrap import ensure_camera_zone

        settings = get_settings()
        try:
            async with async_session_factory() as session:
                camera = await session.get(Camera, self.camera_id)
                if camera is None:
                    return detected
                zone_id = await ensure_camera_zone(session, camera)
                existing = (await session.execute(select(Seat).where(Seat.zone_id == zone_id))).scalars().all()
                known = [s for s in existing if s.source == "DETECTED"]

                pairs = []
                for ni, new in enumerate(detected):
                    for oi, old in enumerate(known):
                        old_box = [old.x_coordinate or 0, old.y_coordinate or 0,
                                   (old.x_coordinate or 0) + (old.width or 0), (old.y_coordinate or 0) + (old.height or 0)]
                        score = iou(new.box, old_box)
                        if score >= settings.SEAT_MATCH_IOU:
                            pairs.append((score, ni, oi))
                pairs.sort(reverse=True)
                used_new: set = set()
                used_old: set = set()
                matched_old_ids: set = set()
                for _score, ni, oi in pairs:
                    if ni in used_new or oi in used_old:
                        continue
                    used_new.add(ni)
                    used_old.add(oi)
                    old, new = known[oi], detected[ni]
                    old.x_coordinate, old.y_coordinate = float(new.x1), float(new.y1)
                    old.width, old.height = float(new.x2 - new.x1), float(new.y2 - new.y1)
                    old.confidence = new.confidence
                    old.is_active = True
                    new.seat_id, new.seat_label = str(old.id), old.seat_label
                    matched_old_ids.add(old.id)

                taken = {s.seat_label for s in existing}
                next_no = max([_label_number(lbl) for lbl in taken] + [0]) + 1
                created = 0
                for ni, new in enumerate(detected):
                    if ni in used_new:
                        continue
                    label = f"S{next_no:02d}"
                    while label in taken:
                        next_no += 1
                        label = f"S{next_no:02d}"
                    taken.add(label)
                    next_no += 1
                    new.seat_label = label
                    session.add(Seat(
                        id=uuid.UUID(new.seat_id),
                        zone_id=zone_id,
                        seat_label=label,
                        x_coordinate=float(new.x1),
                        y_coordinate=float(new.y1),
                        width=float(new.x2 - new.x1),
                        height=float(new.y2 - new.y1),
                        is_active=True,
                        source="DETECTED",
                        confidence=new.confidence,
                    ))
                    created += 1

                deactivated = 0
                for s in existing:
                    if s.is_active and s.id not in matched_old_ids:
                        s.is_active = False
                        deactivated += 1

                cfg = dict(camera.config or {})
                cfg.update({"frame_w": self.frame_w, "frame_h": self.frame_h})
                camera.config = cfg
                camera.resolution_width = self.frame_w
                camera.resolution_height = self.frame_h
                await session.commit()
                logger.info(
                    f"[{self.camera_id}] Seats synced: {len(used_new)} matched, {created} new, {deactivated} deactivated"
                )
        except Exception as e:
            logger.error(f"[{self.camera_id}] Failed to persist detected seats: {e}")
        return sorted(detected, key=lambda s: (_label_number(s.seat_label), s.seat_label))

    # ─── Events & broadcasting ──────────────────────────────────────────────

    def _event_row(self, seat, status, video_ts, confidence, bbox, source: EventSource) -> Dict[str, Any]:
        bbox_dict = None
        if bbox and len(bbox) >= 4:
            bbox_dict = {"x": bbox[0], "y": bbox[1], "w": bbox[2] - bbox[0], "h": bbox[3] - bbox[1]}
        return {
            "seat_id": seat.seat_id,
            "status": status,
            "confidence": confidence,
            "detected_at": _now(),
            "person_bbox": bbox_dict,
            "video_ts": video_ts,
            "source": source.value,
        }

    async def _record_transition(self, seat, prev, status, video_ts, confidence, bbox, source: EventSource) -> None:
        if source == EventSource.VIDEO and video_ts is not None:
            self.session_transitions.append((seat.seat_id, status, video_ts))
        await self._events.put(self._event_row(seat, status, video_ts, confidence, bbox, source))
        if prev is None:
            return  # initial observation, not a change
        item = {
            "seat_id": seat.seat_id,
            "label": seat.seat_label,
            "from": prev,
            "to": status,
            "video_ts": round(video_ts, 2) if video_ts is not None else None,
            "at": _now().isoformat(),
            "demo": source != EventSource.VIDEO,
        }
        self.recent_transitions.appendleft(item)
        await ws_manager.broadcast({"type": "seat_transition", "camera_id": str(self.camera_id), "session_id": self.session_id, **item})

    async def _event_writer(self) -> None:
        """Single writer that batches inserts — avoids SQLite lock contention."""
        done = False
        while not done:
            item = await self._events.get()
            if item is None:
                break
            batch = [item]
            await asyncio.sleep(0.25)
            while not self._events.empty():
                nxt = self._events.get_nowait()
                if nxt is None:
                    done = True
                    break
                batch.append(nxt)
            await self._flush(batch)
        # drain anything left
        rest = []
        while not self._events.empty():
            nxt = self._events.get_nowait()
            if nxt is not None:
                rest.append(nxt)
        if rest:
            await self._flush(rest)

    async def _flush(self, batch: List[Dict[str, Any]]) -> None:
        for attempt in range(3):
            try:
                async with async_session_factory() as session:
                    for row in batch:
                        session.add(OccupancyEvent(
                            seat_id=uuid.UUID(row["seat_id"]),
                            camera_id=self.camera_id,
                            status=OccupancyStatus(row["status"]),
                            confidence=row["confidence"],
                            detected_at=row["detected_at"],
                            person_bbox=row["person_bbox"],
                            session_id=self.session_db_id if row["source"] == EventSource.VIDEO.value else None,
                            source=row["source"],
                            video_ts=row["video_ts"],
                        ))
                    await session.commit()
                return
            except Exception as e:
                logger.warning(f"[{self.camera_id}] Event write attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(0.5 * (attempt + 1))

    async def _update_session(self, **fields: Any) -> None:
        if not self.session_db_id:
            return
        try:
            async with async_session_factory() as session:
                row = await session.get(AnalysisSession, self.session_db_id)
                if row is None:
                    return
                for k, v in fields.items():
                    setattr(row, k, v)
                await session.commit()
        except Exception as e:
            logger.warning(f"[{self.camera_id}] Session update failed: {e}")

    async def _broadcast_status(self) -> None:
        await ws_manager.broadcast({
            "type": "status_update",
            "camera_id": str(self.camera_id),
            "session_id": self.session_id,
            "status": self.status,
            "stage": self.stage,
            "demo": self.mode == "mock",
        })

    async def _broadcast_seat_layout(self) -> None:
        await ws_manager.broadcast({
            "type": "seat_layout",
            "camera_id": str(self.camera_id),
            "session_id": self.session_id,
            "frame_w": self.frame_w,
            "frame_h": self.frame_h,
            "demo": self.mode == "mock",
            "seats": self.seat_payload(),
        })

    async def _broadcast_full_matrix(self) -> None:
        await ws_manager.broadcast({
            "type": "seat_matrix",
            "camera_id": str(self.camera_id),
            "demo": self.mode == "mock",
            "seats": [
                {"seat_id": s.seat_id, "label": s.seat_label, "status": self.seat_states.get(s.seat_id, "VACANT")}
                for s in self.detected_seats
            ],
        })


# ─── Camera Manager ────────────────────────────────────────────────────────────

class CameraManager:
    def __init__(self) -> None:
        self.consumers: Dict[uuid.UUID, VideoCaptureConsumer] = {}

    async def start_camera(
        self,
        camera_id: uuid.UUID,
        mode: str = "mock",
        video_path: Optional[str] = None,
        session_db_id: Optional[uuid.UUID] = None,
        source_filename: Optional[str] = None,
    ) -> VideoCaptureConsumer:
        await self.stop_camera(camera_id)
        consumer = VideoCaptureConsumer(
            camera_id=camera_id,
            mode=mode,
            video_path=video_path,
            session_db_id=session_db_id,
            source_filename=source_filename,
        )
        self.consumers[camera_id] = consumer
        await consumer.start()
        logger.info(f"CameraManager: started camera {camera_id} in {mode} mode")
        return consumer

    async def stop_camera(self, camera_id: uuid.UUID) -> None:
        consumer = self.consumers.get(camera_id)
        if consumer is not None:
            await consumer.stop()
            # Keep the finished consumer so its final frame and summary stay visible.

    async def start_all(self) -> None:
        """Start demo simulations when DEMO_MODE is on. Video runs are never auto-resumed."""
        settings = get_settings()
        if not settings.DEMO_MODE:
            return
        async with async_session_factory() as session:
            cameras = (await session.execute(select(Camera).where(Camera.is_active.is_(True)))).scalars().all()
        for camera in cameras:
            mode = (camera.config or {}).get("source_type", "mock")
            if mode == "mock":
                await self.start_camera(camera_id=camera.id, mode="mock")

    async def stop_all(self) -> None:
        for camera_id in list(self.consumers.keys()):
            await self.stop_camera(camera_id)


camera_manager = CameraManager()
