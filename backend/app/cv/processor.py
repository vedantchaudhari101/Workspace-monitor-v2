"""Computer Vision seat occupancy processor.

Two pipelines live here and share the same public interface:

``report`` (default)
    The pipeline described in the project report:

    * Phase 1 — automated spatial calibration over the first
      ``CALIBRATION_FRAMES`` frames: geometry gates, clean/mixed frame pools,
      adaptive (size-scaled) spatial clustering, a persistence filter, a
      static-object veto (monitors/laptops misread as chairs) and post-cluster
      NMS so each physical chair maps to exactly one seat.
    * Phase 2 — occupancy tracking with torso-segment projection
      (``HIP_WEIGHT``), a velocity gate that ignores walking people
      (``VELOCITY_GATE_PX``), exclusive ownership arbitration (each torso can
      credit at most one seat, with a ``CROSS_EXPAND`` cross-axis check) and a
      counter-based hysteresis state machine (``OCC_FRAMES`` / ``CLEAR_FRAMES``).
      The original hip/knee posture check is kept as an additional gate, which
      targets the report's "standing in front of a desk" limitation.

``legacy``
    The original repository pipeline (IoU clustering over the first seconds,
    containment + posture heuristics). Kept intact so behaviour can be compared
    or restored with ``CV_PIPELINE=legacy``.

Classes:
  - ChairDetector: discovers the stable seat layout.
  - SeatOccupancyProcessor: evaluates occupancy on the frozen layout.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from app.models.occupancy_event import OccupancyStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)

SeatResults = Dict[str, Tuple[OccupancyStatus, float, Optional[List[float]]]]


@dataclass
class SeatDefinition:
    """A single detected chair seat with a permanent identity."""

    seat_id: str           # UUID string — stable across sessions when matched (E1)
    seat_label: str        # Human-readable label, e.g. "S01"
    x1: int                # Pixel bounding box coordinates
    y1: int
    x2: int
    y2: int
    track_id: int = 0      # Associated track ID (defaults to 0)
    confidence: float = 0.0

    @property
    def box(self) -> List[int]:
        return [self.x1, self.y1, self.x2, self.y2]

    @property
    def centre(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)


# ─── Model cache ──────────────────────────────────────────────────────────────

_model_cache: Dict[str, Any] = {}


def get_yolo_model(model_path: str):
    """Load (once) and return a YOLO model.

    ``ultralytics`` is imported lazily so the API, tests and geometry helpers do
    not pay the PyTorch import cost unless a video is actually processed.
    """
    if model_path not in _model_cache:
        from ultralytics import YOLO  # noqa: WPS433 — deliberate lazy import

        logger.info(f"Global Model Cache: Loading YOLO model {model_path} from disk...")
        try:
            import torch

            if torch.get_num_threads() > 4:
                torch.set_num_threads(4)
        except Exception as e:  # pragma: no cover — optional optimisation
            logger.debug(f"PyTorch thread optimization skipped: {e}")

        _model_cache[model_path] = YOLO(model_path)
        logger.info(f"Global Model Cache: YOLO model {model_path} loaded successfully.")
    return _model_cache[model_path]


# ─── Geometry helpers ─────────────────────────────────────────────────────────


def iou(a: List[float], b: List[float]) -> float:
    """Intersection over Union of two xyxy boxes."""
    ix1 = max(a[0], b[0]); iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2]); iy2 = min(a[3], b[3])
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def passes_geometry_gate(box: List[float], frame_w: int, frame_h: int) -> bool:
    """Reject detections whose size or shape cannot be a chair."""
    w = box[2] - box[0]
    h = box[3] - box[1]
    if w <= 1 or h <= 1:
        return False
    area_frac = (w * h) / float(max(1, frame_w * frame_h))
    aspect = w / h
    return 0.0008 <= area_frac <= 0.25 and 0.25 <= aspect <= 4.0


def merge_radius(w: float, h: float) -> float:
    """Report §5.1: merge radius scales with the detection's own size."""
    return min(w, h) * 0.50


@dataclass
class _Cluster:
    boxes: List[List[float]] = field(default_factory=list)
    confs: List[float] = field(default_factory=list)
    frames: set = field(default_factory=set)
    cx: float = 0.0
    cy: float = 0.0
    radius: float = 0.0

    def add(self, box: List[float], conf: float, frame_idx: int) -> None:
        self.boxes.append(box)
        self.confs.append(conf)
        self.frames.add(frame_idx)
        n = len(self.boxes)
        bx = (box[0] + box[2]) / 2.0
        by = (box[1] + box[3]) / 2.0
        self.cx += (bx - self.cx) / n
        self.cy += (by - self.cy) / n

    @property
    def peak_conf(self) -> float:
        return max(self.confs) if self.confs else 0.0

    def median_box(self) -> List[int]:
        arr = np.array(self.boxes, dtype=float)
        return [int(round(v)) for v in np.median(arr, axis=0).tolist()]


def adaptive_cluster(detections: List[Tuple[int, List[float], float]]) -> List[_Cluster]:
    """Greedy, confidence-ordered clustering with a size-scaled merge radius.

    ``detections`` is a list of ``(frame_idx, box, conf)``.
    """
    clusters: List[_Cluster] = []
    for frame_idx, box, conf in sorted(detections, key=lambda d: d[2], reverse=True):
        bx = (box[0] + box[2]) / 2.0
        by = (box[1] + box[3]) / 2.0
        best: Optional[_Cluster] = None
        best_d = math.inf
        for c in clusters:
            d = math.hypot(bx - c.cx, by - c.cy)
            if d <= c.radius and d < best_d:
                best, best_d = c, d
        if best is None:
            best = _Cluster(radius=merge_radius(box[2] - box[0], box[3] - box[1]))
            clusters.append(best)
        best.add(box, conf, frame_idx)
    return clusters


def overlap_ratio(a: List[float], b: List[float]) -> float:
    """Intersection divided by the smaller box's area (1.0 = one box inside the other)."""
    ix1 = max(a[0], b[0]); iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2]); iy2 = min(a[3], b[3])
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return inter / smaller if smaller > 0 else 0.0


def post_cluster_nms(clusters: List[_Cluster], frame_w: int, frame_h: int, frac: float = 0.06) -> Tuple[List[_Cluster], int]:
    """Collapse clusters that describe the same physical chair.

    Report §5.1 stage 3: centres within ``frac`` of the frame's shorter side are
    duplicates. Two box-level checks are added for the same reason: YOLO
    sometimes reports a chair twice at different extents (e.g. seat only vs.
    seat + desk), which moves the centres apart but leaves one box inside the
    other. The higher-confidence cluster is kept.
    """
    limit = frac * min(frame_w, frame_h)
    kept: List[_Cluster] = []
    suppressed = 0
    for c in sorted(clusters, key=lambda c: c.peak_conf, reverse=True):
        cb = c.median_box()
        duplicate = False
        for k in kept:
            kb = k.median_box()
            if (
                math.hypot(c.cx - k.cx, c.cy - k.cy) < limit
                or iou(cb, kb) > 0.45
                or overlap_ratio(cb, kb) > 0.75
            ):
                duplicate = True
                break
        if duplicate:
            suppressed += 1
            continue
        kept.append(c)
    return kept, suppressed


def sort_row_major(seats: List[SeatDefinition]) -> List[SeatDefinition]:
    """Order seats top-to-bottom in bands, then left-to-right."""
    if not seats:
        return seats
    band = max(40.0, float(np.median([s.y2 - s.y1 for s in seats])) * 0.6)
    return sorted(seats, key=lambda s: (int(s.centre[1] // band), s.centre[0]))


# ─── Phase 1: calibration ─────────────────────────────────────────────────────


class ChairDetector:
    """Detects the stable physical seat layout from the start of a video."""

    PERSON_CLASS = 0
    CHAIR_CLASS = 56
    COUCH_CLASS = 57
    TV_CLASS = 62
    LAPTOP_CLASS = 63

    def __init__(self, model_path: str = "yolov8n.pt") -> None:
        self.model = get_yolo_model(model_path)

    # -- Report pipeline -------------------------------------------------------

    def calibrate(
        self,
        video_path: str,
        max_frames: int = 150,
        skip: int = 3,
        conf_threshold: float = 0.20,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Tuple[List[SeatDefinition], Dict[str, Any]]:
        """Run the report's three-stage calibration and return seats + diagnostics."""
        import cv2

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"ChairDetector: Failed to open video file {video_path}")
            return [], {"error": "unreadable video"}

        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or max_frames
        max_frames = min(max_frames, total) if total > 0 else max_frames

        clean: List[Tuple[int, List[float], float]] = []
        mixed: List[Tuple[int, List[float], float]] = []
        statics: List[Tuple[int, List[float], float]] = []
        clean_frames: set = set()
        sampled_clean = 0
        sampled_total = 0
        raw = 0
        gated = 0
        frames_scanned = 0

        while frames_scanned < max_frames:
            if is_cancelled and is_cancelled():
                break
            ret, frame = cap.read()
            if not ret:
                break
            frames_scanned += 1
            if progress_callback:
                progress_callback(frames_scanned, max_frames)
            if (frames_scanned - 1) % max(1, skip) != 0:
                continue
            if not frame_w or not frame_h:
                frame_h, frame_w = frame.shape[:2]

            results = self.model(
                frame,
                classes=[self.PERSON_CLASS, self.CHAIR_CLASS, self.COUCH_CLASS, self.TV_CLASS, self.LAPTOP_CLASS],
                conf=conf_threshold,
                imgsz=1280,
                verbose=False,
            )
            if not results or results[0].boxes is None:
                continue
            boxes = results[0].boxes
            xyxy = boxes.xyxy.cpu().numpy().tolist()
            cls = boxes.cls.cpu().numpy().astype(int).tolist()
            confs = boxes.conf.cpu().numpy().tolist()

            has_person = any(c == self.PERSON_CLASS for c in cls)
            sampled_total += 1
            if not has_person:
                sampled_clean += 1

            for box, c, cf in zip(xyxy, cls, confs):
                if c in (self.TV_CLASS, self.LAPTOP_CLASS):
                    statics.append((frames_scanned, box, cf))
                    continue
                if c not in (self.CHAIR_CLASS, self.COUCH_CLASS):
                    continue
                raw += 1
                if not passes_geometry_gate(box, frame_w, frame_h):
                    gated += 1
                    continue
                if has_person:
                    mixed.append((frames_scanned, box, cf))
                else:
                    clean.append((frames_scanned, box, cf))
                    clean_frames.add(frames_scanned)

        cap.release()

        # Stage 1 — multi-window accumulation: prefer person-free frames.
        use_clean = len(clean_frames) >= 8
        pool = clean if use_clean else clean + mixed
        pool_frames = sampled_clean if use_clean else sampled_total

        # Stage 2 — adaptive clustering + persistence filter (>= 15% of pool frames).
        clusters = adaptive_cluster(pool)
        min_frames = max(2, math.ceil(0.15 * max(1, pool_frames)))
        persistent = [c for c in clusters if len(c.frames) >= min_frames]

        # Static-object veto — monitors/laptops that YOLO occasionally labels as chairs.
        static_clusters = [
            c for c in adaptive_cluster(statics) if len(c.frames) >= min_frames
        ]
        vetoed = 0
        survivors: List[_Cluster] = []
        for c in persistent:
            mb = c.median_box()
            if any(iou(mb, s.median_box()) > 0.45 for s in static_clusters):
                vetoed += 1
                continue
            survivors.append(c)

        # Stage 3 — post-cluster NMS (centres within 6% of the shorter side).
        kept, suppressed = post_cluster_nms(survivors, frame_w or 1, frame_h or 1)

        seats = [
            SeatDefinition(
                seat_id=str(uuid.uuid4()),
                seat_label="",
                x1=b[0], y1=b[1], x2=b[2], y2=b[3],
                confidence=round(c.peak_conf, 3),
            )
            for c in kept
            for b in [c.median_box()]
        ]
        seats = sort_row_major(seats)
        for idx, s in enumerate(seats, start=1):
            s.seat_label = f"S{idx:02d}"

        meta = {
            "frames_scanned": frames_scanned,
            "frames_sampled": sampled_total,
            "person_free_frames": sampled_clean,
            "pool": "clean" if use_clean else "combined",
            "raw_detections": raw,
            "geometry_rejected": gated,
            "clusters": len(clusters),
            "persistent_clusters": len(persistent),
            "static_vetoed": vetoed,
            "nms_suppressed": suppressed,
            "seats": len(seats),
            "frame_w": frame_w,
            "frame_h": frame_h,
        }
        logger.info(f"ChairDetector.calibrate: {meta}")
        return seats, meta

    # -- Legacy pipeline (unchanged behaviour) ----------------------------------

    def detect_chairs_multi_frame(
        self,
        video_path: str,
        duration_sec: float = 6.0,
        conf_threshold: float = 0.20,
        skip: int = 5,
        progress_callback: Optional[Callable] = None,
        is_cancelled: Optional[Callable] = None,
    ) -> List[SeatDefinition]:
        """Original IoU-clustering calibration over the first seconds of video."""
        import cv2

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"ChairDetector: Failed to open video file {video_path}")
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        max_frames = int(fps * duration_sec)
        all_raw_boxes: List[List[int]] = []
        frames_scanned = 0
        inferences_run = 0

        while frames_scanned < max_frames:
            if is_cancelled and is_cancelled():
                break
            ret, frame = cap.read()
            if not ret:
                break
            frames_scanned += 1
            if progress_callback:
                progress_callback(frames_scanned, max_frames)
            if (frames_scanned - 1) % skip != 0:
                continue
            inferences_run += 1
            results = self.model(
                frame,
                classes=[self.CHAIR_CLASS, self.COUCH_CLASS],
                conf=conf_threshold,
                imgsz=1280,
                verbose=False,
            )
            if not results or results[0].boxes is None:
                continue
            for xyxy in results[0].boxes.xyxy.cpu().numpy().tolist():
                all_raw_boxes.append(list(map(int, xyxy)))
        cap.release()

        clusters: List[List[List[int]]] = []
        for box in all_raw_boxes:
            matched = False
            for cluster in clusters:
                avg_box = [int(sum(b[i] for b in cluster) / len(cluster)) for i in range(4)]
                if iou(box, avg_box) > 0.35:
                    cluster.append(box)
                    matched = True
                    break
            if not matched:
                clusters.append([box])

        min_votes = max(3, int(inferences_run * 0.15))
        stable: List[SeatDefinition] = []
        for cluster in clusters:
            if len(cluster) < min_votes:
                continue
            mb = [sorted(b[i] for b in cluster)[len(cluster) // 2] for i in range(4)]
            stable.append(SeatDefinition(
                seat_id=str(uuid.uuid4()), seat_label="",
                x1=mb[0], y1=mb[1], x2=mb[2], y2=mb[3],
            ))
        stable = sort_row_major(stable)
        for idx, s in enumerate(stable, start=1):
            s.seat_label = f"S{idx:02d}"
        logger.info(f"ChairDetector (legacy): Found {len(stable)} stable physical chairs.")
        return stable


# ─── Phase 2: occupancy ───────────────────────────────────────────────────────


def _kp_point(kp: np.ndarray, kconf: Optional[np.ndarray], idx: int, min_conf: float = 0.3) -> Optional[Tuple[float, float]]:
    x, y = float(kp[idx][0]), float(kp[idx][1])
    if x == 0.0 and y == 0.0:
        return None
    if kconf is not None and float(kconf[idx]) < min_conf:
        return None
    return (x, y)


def _midpoint(a: Optional[Tuple[float, float]], b: Optional[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
    if a and b:
        return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    return a or b


def torso_point(
    box: List[float],
    kp: Optional[np.ndarray],
    kconf: Optional[np.ndarray] = None,
    hip_weight: float = 0.70,
) -> Tuple[Tuple[float, float], str]:
    """Report §5.2 innovation 1: weighted point on the shoulder→hip segment.

    Returns the point and how it was obtained (``torso`` | ``hips`` |
    ``shoulders`` | ``box``) so overlays and tests can tell estimates apart.
    """
    if kp is not None and len(kp) >= 13:
        shoulders = _midpoint(_kp_point(kp, kconf, 5), _kp_point(kp, kconf, 6))
        hips = _midpoint(_kp_point(kp, kconf, 11), _kp_point(kp, kconf, 12))
        if shoulders and hips:
            return (
                (shoulders[0] + hip_weight * (hips[0] - shoulders[0]),
                 shoulders[1] + hip_weight * (hips[1] - shoulders[1])),
                "torso",
            )
        if hips:
            return hips, "hips"
        if shoulders:
            # Project roughly one torso-length downward towards the seat.
            torso_len = 0.30 * (box[3] - box[1])
            return (shoulders[0], shoulders[1] + hip_weight * torso_len), "shoulders"
    return (((box[0] + box[2]) / 2.0), box[1] + 0.6 * (box[3] - box[1])), "box"


def row_axis(seats: List[SeatDefinition]) -> str:
    """Dominant row direction of the layout: 'x' (side view) or 'y' (overhead)."""
    if len(seats) < 2:
        return "x"
    xs = np.array([s.centre[0] for s in seats])
    ys = np.array([s.centre[1] for s in seats])
    mw = float(np.mean([s.x2 - s.x1 for s in seats])) or 1.0
    mh = float(np.mean([s.y2 - s.y1 for s in seats])) or 1.0
    return "x" if (xs.std() / mw) >= (ys.std() / mh) else "y"


def assign_owner(
    point: Tuple[float, float],
    seats: List[SeatDefinition],
    axis: str,
    cross_expand: float = 0.30,
) -> Optional[SeatDefinition]:
    """Report §5.2 innovation 2: the single seat that owns this torso, if any.

    Candidates must contain the point on the cross axis (seat extent expanded
    by ``cross_expand`` on both sides) and lie within the seat's expanded extent
    on the row axis. The nearest candidate along the row axis wins, so one
    person can never credit two seats.
    """
    px, py = point
    best: Optional[SeatDefinition] = None
    best_key = (math.inf, math.inf)
    for s in seats:
        cx, cy = s.centre
        w = s.x2 - s.x1
        h = s.y2 - s.y1
        if axis == "x":
            along, cross = abs(px - cx), abs(py - cy)
            along_limit = w * (0.5 + cross_expand)
            in_cross = (s.y1 - cross_expand * h) <= py <= (s.y2 + cross_expand * h)
        else:
            along, cross = abs(py - cy), abs(px - cx)
            along_limit = h * (0.5 + cross_expand)
            in_cross = (s.x1 - cross_expand * w) <= px <= (s.x2 + cross_expand * w)
        if not in_cross or along > along_limit:
            continue
        key = (along, cross)
        if key < best_key:
            best, best_key = s, key
    return best


class SeatOccupancyProcessor:
    """Evaluates occupancy on predefined, frozen seat bounding boxes."""

    def __init__(
        self,
        model_path: str = "yolov8n-pose.pt",
        containment_threshold: float = 0.35,
        aspect_ratio_threshold: float = 0.65,
        pipeline: str = "report",
        occ_frames: int = 15,
        clear_frames: int = 10,
        velocity_gate_px: float = 32.0,
        hip_weight: float = 0.70,
        cross_expand: float = 0.30,
        load_model: bool = True,
    ) -> None:
        self.pose_model = get_yolo_model(model_path) if load_model else None
        self.containment_threshold = containment_threshold
        self.aspect_ratio_threshold = aspect_ratio_threshold
        self.pipeline = pipeline
        self.occ_frames = occ_frames
        self.clear_frames = clear_frames
        self.velocity_gate_px = velocity_gate_px
        self.hip_weight = hip_weight
        self.cross_expand = cross_expand

        self.seat_stable_states: Dict[str, OccupancyStatus] = {}
        self.seat_occupied_counters: Dict[str, int] = {}
        self.seat_vacant_counters: Dict[str, int] = {}
        self.seat_assigned_track_id: Dict[str, Optional[int]] = {}
        self.latest_seat_person_info: Dict[str, Tuple[float, Optional[List[float]]]] = {}

        # Report pipeline state
        self._prev_torso: Dict[int, Tuple[float, float]] = {}
        self._axis_cache: Tuple[Tuple[str, ...], str] = ((), "x")
        self.last_people: List[Dict[str, Any]] = []   # for overlays / diagnostics

    # -- Shared ----------------------------------------------------------------

    def _init_seats(self, seats: List[SeatDefinition]) -> None:
        for s in seats:
            if s.seat_id not in self.seat_stable_states:
                self.seat_stable_states[s.seat_id] = OccupancyStatus.VACANT
                self.seat_occupied_counters[s.seat_id] = 0
                self.seat_vacant_counters[s.seat_id] = 0
                self.seat_assigned_track_id[s.seat_id] = None
                self.latest_seat_person_info[s.seat_id] = (0.0, None)

    def _run_pose(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        results = None
        try:
            results = self.pose_model.track(frame, persist=True, classes=[0], verbose=False, conf=0.3)
        except Exception as e:
            logger.warning(f"YOLO track failed, falling back to detect: {e}")
            try:
                results = self.pose_model(frame, classes=[0], verbose=False, conf=0.3)
            except Exception:
                results = None

        persons: List[Dict[str, Any]] = []
        if results and len(results) > 0:
            r = results[0]
            kps = getattr(r, "keypoints", None)
            box_ids = getattr(r.boxes, "id", None)
            for i, box in enumerate(r.boxes):
                kp_xy = None
                kp_conf = None
                if kps is not None and len(kps) > i:
                    try:
                        kp_xy = kps.xy[i].cpu().numpy()
                        if getattr(kps, "conf", None) is not None:
                            kp_conf = kps.conf[i].cpu().numpy()
                    except Exception:
                        kp_xy = None
                persons.append({
                    "box": box.xyxy[0].cpu().numpy().tolist(),
                    "conf": float(box.conf[0].cpu().item()),
                    "track_id": int(box_ids[i].item()) if box_ids is not None else None,
                    "keypoints": kps[i] if kps is not None and len(kps) > i else None,
                    "kp_xy": kp_xy,
                    "kp_conf": kp_conf,
                })
        return persons

    def _apply_hysteresis(self, seat_id: str, evidence_person: Optional[Dict[str, Any]]) -> None:
        current = self.seat_stable_states[seat_id]
        occupied_evidence = evidence_person is not None
        if current == OccupancyStatus.VACANT:
            if occupied_evidence:
                self.seat_occupied_counters[seat_id] += 1
                self.seat_vacant_counters[seat_id] = 0
                if self.seat_occupied_counters[seat_id] >= self.occ_frames:
                    self.seat_stable_states[seat_id] = OccupancyStatus.OCCUPIED
                    self.seat_assigned_track_id[seat_id] = evidence_person["track_id"]
                    self.latest_seat_person_info[seat_id] = (evidence_person["conf"], evidence_person["box"])
            else:
                self.seat_occupied_counters[seat_id] = 0
                self.seat_vacant_counters[seat_id] += 1
        else:
            if not occupied_evidence:
                self.seat_vacant_counters[seat_id] += 1
                self.seat_occupied_counters[seat_id] = 0
                if self.seat_vacant_counters[seat_id] >= self.clear_frames:
                    self.seat_stable_states[seat_id] = OccupancyStatus.VACANT
                    self.seat_assigned_track_id[seat_id] = None
                    self.latest_seat_person_info[seat_id] = (0.0, None)
            else:
                self.seat_vacant_counters[seat_id] = 0
                self.seat_occupied_counters[seat_id] += 1
                self.seat_assigned_track_id[seat_id] = evidence_person["track_id"]
                self.latest_seat_person_info[seat_id] = (evidence_person["conf"], evidence_person["box"])

    def _results(self, seats: List[SeatDefinition]) -> SeatResults:
        out: SeatResults = {}
        for s in seats:
            conf, bbox = self.latest_seat_person_info[s.seat_id]
            out[s.seat_id] = (self.seat_stable_states[s.seat_id], conf, bbox)
        return out

    def detect_occupancy(self, frame: np.ndarray, seats: List[SeatDefinition]) -> SeatResults:
        """Detect people and update each seat's state machine."""
        self._init_seats(seats)
        persons = self._run_pose(frame)
        frame_h, frame_w = frame.shape[:2]
        if self.pipeline == "legacy":
            return self._detect_legacy(persons, seats)
        return self.evaluate_report(persons, seats, frame_w, frame_h)

    # -- Report pipeline ---------------------------------------------------------

    def _layout_axis(self, seats: List[SeatDefinition]) -> str:
        key = tuple(s.seat_id for s in seats)
        if self._axis_cache[0] != key:
            self._axis_cache = (key, row_axis(seats))
        return self._axis_cache[1]

    def evaluate_report(
        self,
        persons: List[Dict[str, Any]],
        seats: List[SeatDefinition],
        frame_w: int,
        frame_h: int,
    ) -> SeatResults:
        """Ownership + velocity-gated evidence, then hysteresis. Pure given ``persons``."""
        self._init_seats(seats)
        axis = self._layout_axis(seats)
        gate = self.velocity_gate_px * (min(frame_w, frame_h) / 720.0)

        evidence: Dict[str, Dict[str, Any]] = {}
        people: List[Dict[str, Any]] = []
        seen_tracks: set = set()

        for p in persons:
            point, method = torso_point(p["box"], p.get("kp_xy"), p.get("kp_conf"), self.hip_weight)
            walking = False
            tid = p.get("track_id")
            if tid is not None:
                seen_tracks.add(tid)
                prev = self._prev_torso.get(tid)
                if prev is not None and math.hypot(point[0] - prev[0], point[1] - prev[1]) > gate:
                    walking = True
                self._prev_torso[tid] = point

            owner = None
            sitting = False
            if not walking:
                owner = assign_owner(point, seats, axis, self.cross_expand)
                if owner is not None:
                    sitting = self._is_sitting(p["box"], p.get("keypoints"), owner.box)
                    if sitting:
                        prev_ev = evidence.get(owner.seat_id)
                        if prev_ev is None or p["conf"] > prev_ev["conf"]:
                            evidence[owner.seat_id] = p
            people.append({
                "box": p["box"],
                "point": point,
                "method": method,
                "walking": walking,
                "owner": owner.seat_id if owner else None,
                "sitting": sitting,
                "track_id": tid,
            })

        # Forget tracks that left the frame so a re-used id is not gated wrongly.
        for tid in list(self._prev_torso.keys()):
            if tid not in seen_tracks:
                del self._prev_torso[tid]

        for s in seats:
            self._apply_hysteresis(s.seat_id, evidence.get(s.seat_id))

        self.last_people = people
        return self._results(seats)

    # -- Legacy pipeline -----------------------------------------------------------

    def _detect_legacy(self, detected_persons: List[Dict[str, Any]], seats: List[SeatDefinition]) -> SeatResults:
        self.last_people = []
        for seat in seats:
            seat_box = [float(seat.x1), float(seat.y1), float(seat.x2), float(seat.y2)]
            current_stable = self.seat_stable_states[seat.seat_id]
            best_person = None
            best_overlap = 0.0

            assigned_tid = self.seat_assigned_track_id[seat.seat_id]
            if current_stable == OccupancyStatus.OCCUPIED and assigned_tid is not None:
                tracked = next((p for p in detected_persons if p["track_id"] == assigned_tid), None)
                if tracked:
                    overlap = self._intersection_over_seat(tracked["box"], seat_box)
                    if overlap > self.containment_threshold and self._is_sitting(tracked["box"], tracked["keypoints"], seat_box):
                        best_person, best_overlap = tracked, overlap

            if best_person is None:
                for p in detected_persons:
                    overlap = self._intersection_over_seat(p["box"], seat_box)
                    if overlap > self.containment_threshold and self._is_sitting(p["box"], p["keypoints"], seat_box):
                        if overlap > best_overlap:
                            best_person, best_overlap = p, overlap

            self._apply_hysteresis(seat.seat_id, best_person)
        return self._results(seats)

    # -- Drawing -------------------------------------------------------------------

    # BGR colours matching the UI tokens: occupied #FF5A5F, available #2ED47A,
    # person/system accent #7FDBF0.
    COLOR_OCCUPIED = (95, 90, 255)
    COLOR_AVAILABLE = (122, 212, 46)
    COLOR_PERSON = (240, 219, 127)
    COLOR_WALKING = (150, 150, 150)

    def draw_overlays(self, frame: np.ndarray, seats: List[SeatDefinition], results: SeatResults) -> np.ndarray:
        """Draw seat boxes (red = occupied, green = available), labels and torso points."""
        import cv2

        annotated = frame
        h, w = annotated.shape[:2]
        scale = max(1.0, min(w, h) / 720.0)
        thick = max(2, int(round(2 * scale)))
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5 * scale
        text_th = max(1, int(round(scale)))

        for p in self.last_people:
            px, py = int(p["point"][0]), int(p["point"][1])
            color = self.COLOR_WALKING if p["walking"] else self.COLOR_PERSON
            cv2.circle(annotated, (px, py), max(3, int(4 * scale)), color, -1, lineType=cv2.LINE_AA)

        for seat in seats:
            status, _conf, person_box = results.get(seat.seat_id, (OccupancyStatus.VACANT, 0.0, None))
            occupied = status == OccupancyStatus.OCCUPIED
            if occupied and person_box:
                px1, py1, px2, py2 = map(int, person_box)
                cv2.rectangle(annotated, (px1, py1), (px2, py2), self.COLOR_PERSON, max(1, thick - 1), lineType=cv2.LINE_AA)

            color = self.COLOR_OCCUPIED if occupied else self.COLOR_AVAILABLE
            cv2.rectangle(annotated, (seat.x1, seat.y1), (seat.x2, seat.y2), color, thick, lineType=cv2.LINE_AA)

            label = seat.seat_label
            (tw, th), _ = cv2.getTextSize(label, font, font_scale, text_th)
            pad = int(4 * scale)
            lx1, ly1 = seat.x1, max(0, seat.y1 - th - 2 * pad)
            cv2.rectangle(annotated, (lx1, ly1), (lx1 + tw + 2 * pad, seat.y1), color, -1)
            cv2.putText(annotated, label, (lx1 + pad, seat.y1 - pad), font, font_scale, (18, 16, 14), text_th, lineType=cv2.LINE_AA)

        return annotated

    def process_frame(self, frame: np.ndarray, seats: List[SeatDefinition]) -> Tuple[SeatResults, np.ndarray]:
        """Backward-compatible process method."""
        results = self.detect_occupancy(frame, seats)
        return results, self.draw_overlays(frame, seats, results)

    # -- Heuristics (unchanged) -------------------------------------------------------

    def _intersection_over_seat(self, person_box: List[float], seat_box: List[float]) -> float:
        """Fraction of the seat area covered by the person box."""
        px1, py1, px2, py2 = person_box
        sx1, sy1, sx2, sy2 = seat_box
        ix1 = max(px1, sx1); iy1 = max(py1, sy1)
        ix2 = min(px2, sx2); iy2 = min(py2, sy2)
        if ix2 <= ix1 or iy2 <= iy1:
            return 0.0
        inter = (ix2 - ix1) * (iy2 - iy1)
        seat_area = (sx2 - sx1) * (sy2 - sy1)
        return inter / seat_area if seat_area > 0 else 0.0

    def _is_sitting(self, person_box: List[float], keypoints: Any, seat_box: Optional[List[float]] = None) -> bool:
        """Sitting-posture check from hip/knee geometry with box-based fallbacks."""
        px1, py1, px2, py2 = person_box
        w = px2 - px1
        h = py2 - py1
        aspect = w / h if h > 0 else 0.0

        has_pose = False
        if keypoints is not None and hasattr(keypoints, "xy") and len(keypoints.xy) > 0:
            try:
                kp = keypoints.xy[0].cpu().numpy() if hasattr(keypoints.xy[0], "cpu") else keypoints.xy[0]
                if kp.shape[0] >= 17:
                    l_hip, r_hip = kp[11], kp[12]
                    l_knee, r_knee = kp[13], kp[14]
                    has_l_hip = float(l_hip[0]) != 0.0 or float(l_hip[1]) != 0.0
                    has_r_hip = float(r_hip[0]) != 0.0 or float(r_hip[1]) != 0.0
                    has_l_knee = float(l_knee[0]) != 0.0 or float(l_knee[1]) != 0.0
                    has_r_knee = float(r_knee[0]) != 0.0 or float(r_knee[1]) != 0.0

                    if (has_l_hip or has_r_hip) and (has_l_knee or has_r_knee):
                        has_pose = True
                        hips = [p for p, ok in ((l_hip, has_l_hip), (r_hip, has_r_hip)) if ok]
                        knees = [p for p, ok in ((l_knee, has_l_knee), (r_knee, has_r_knee)) if ok]
                        hip_y = sum(float(p[1]) for p in hips) / len(hips)
                        knee_y = sum(float(p[1]) for p in knees) / len(knees)
                        if abs(knee_y - hip_y) / (h + 1e-5) < 0.35:
                            return True
                        for hip, knee, has_h, has_k in (
                            (l_hip, l_knee, has_l_hip, has_l_knee),
                            (r_hip, r_knee, has_r_hip, has_r_knee),
                        ):
                            if has_h and has_k:
                                dy = abs(float(knee[1]) - float(hip[1]))
                                dx = abs(float(knee[0]) - float(hip[0])) + 1e-5
                                if dy / dx < 1.0:
                                    return True
            except Exception as e:
                logger.warning(f"Error in pose keypoint evaluation: {e}")

        if not has_pose and seat_box is not None:
            sx1, sy1, sx2, sy2 = seat_box
            sh = sy2 - sy1
            py_mid = (py1 + py2) / 2.0
            py_bottom_ok = py2 <= sy2 + sh * 0.6
            py_centroid_ok = (sy1 - sh * 0.3) <= py_mid <= (sy2 + sh * 0.3)
            aspect_ok = aspect >= self.aspect_ratio_threshold - 0.1
            if py_bottom_ok and py_centroid_ok and aspect_ok:
                return True

        return aspect >= self.aspect_ratio_threshold
