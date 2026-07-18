"""Computer Vision seat occupancy processor.

Provides classes:
  - ChairDetector: Scans the first few seconds of a video to detect physical
    chairs, clusters overlapping detections, and freezes the stable seat layout.
  - SeatOccupancyProcessor: Evaluates occupancy by checking overlap between
    detected persons and the frozen seat regions during video playback.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import List, Dict, Tuple, Any, Optional
import numpy as np
from ultralytics import YOLO

from app.models.occupancy_event import OccupancyStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SeatDefinition:
    """A single detected chair seat with a permanent in-memory identity."""
    seat_id: str           # UUID string, stable for the entire video session
    seat_label: str        # Human-readable: "Seat 1", "Seat 2", ...
    x1: int                # Pixel bounding box coordinates
    y1: int
    x2: int
    y2: int
    track_id: int          # Associated track ID (defaults to 0)

    @property
    def box(self) -> List[int]:
        return [self.x1, self.y1, self.x2, self.y2]


# Global model weights cache to prevent redundant disk loads and memory bloat
_model_cache: Dict[str, YOLO] = {}

def get_yolo_model(model_path: str) -> YOLO:
    if model_path not in _model_cache:
        logger.info(f"Global Model Cache: Loading YOLO model {model_path} from disk...")
        # Apply thread optimization before loading PyTorch model
        try:
            import torch
            if torch.get_num_threads() > 4:
                torch.set_num_threads(4)
                logger.info(f"Global Model Cache: Limit PyTorch CPU threads to 4 for {model_path}.")
        except Exception as e:
            logger.debug(f"PyTorch thread optimization skipped: {e}")
        
        _model_cache[model_path] = YOLO(model_path)
        logger.info(f"Global Model Cache: YOLO model {model_path} loaded successfully.")
    else:
        logger.info(f"Global Model Cache: Reusing cached YOLO model {model_path}.")
    return _model_cache[model_path]


class ChairDetector:
    """
    Detects physical chairs by scanning the first few seconds of video,
    clustering overlapping detections across frames to build a stable layout.
    """

    CHAIR_CLASS = 56
    COUCH_CLASS = 57
    PERSON_CLASS = 0

    def __init__(self, model_path: str = "yolov8n.pt") -> None:
        """Loads the YOLO detection model."""
        self.model = get_yolo_model(model_path)

    def detect_chairs_multi_frame(
        self,
        video_path: str,
        duration_sec: float = 6.0,
        conf_threshold: float = 0.20,
        skip: int = 5,
        progress_callback: Optional[callable] = None,
        is_cancelled: Optional[callable] = None,
    ) -> List[SeatDefinition]:
        """
        Scans several seconds of video, aggregates raw chair detections,
        performs spatial IoU clustering, and produces a single stable room map.
        """
        import cv2

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"ChairDetector: Failed to open video file {video_path}")
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        max_frames = int(fps * duration_sec)
        logger.info(f"ChairDetector: Scanning first {max_frames} frames (skip={skip})...")

        all_raw_boxes: List[List[int]] = []
        frames_scanned = 0
        inferences_run = 0

        while frames_scanned < max_frames:
            if is_cancelled and is_cancelled():
                logger.info("ChairDetector: Scan cancelled cooperatively.")
                break

            ret, frame = cap.read()
            if not ret:
                break

            frames_scanned += 1

            if progress_callback:
                progress_callback(frames_scanned, max_frames)

            # Frame skipping logic
            if (frames_scanned - 1) % skip != 0:
                continue

            inferences_run += 1

            # Run YOLO detection for chairs (56) and couches (57)
            # Pass imgsz=1280 to preserve small chair details in UHD (4K) streams
            results = self.model(
                frame,
                classes=[self.CHAIR_CLASS, self.COUCH_CLASS],
                conf=conf_threshold,
                imgsz=1280,
                verbose=False
            )

            if not results:
                continue

            r = results[0]
            boxes = r.boxes
            if boxes is None:
                continue

            xyxy_list = boxes.xyxy.cpu().numpy().tolist()
            for xyxy in xyxy_list:
                all_raw_boxes.append(list(map(int, xyxy)))

        cap.release()

        # Spatial clustering (group overlapping boxes into physical chairs)
        clusters: List[List[List[int]]] = []

        for box in all_raw_boxes:
            matched = False
            for cluster in clusters:
                # Compare with the average box of the cluster
                avg_box = [int(sum(b[i] for b in cluster) / len(cluster)) for i in range(4)]
                # Optimized IoU threshold (0.35) to robustly group jittery detections of same physical chair
                if self._iou(box, avg_box) > 0.35:
                    cluster.append(box)
                    matched = True
                    break
            
            if not matched:
                clusters.append([box])

        # Filter clusters: keep only clusters with enough votes (at least 15% of frames scanned with YOLO)
        min_votes = max(3, int(inferences_run * 0.15))
        stable_seats: List[SeatDefinition] = []

        # Sort clusters row-by-row (top-to-bottom), then left-to-right
        def cluster_key(c):
            avg_x = sum(b[0] for b in c) / len(c)
            avg_y = sum(b[1] for b in c) / len(c)
            return (avg_y // 80, avg_x)

        sorted_clusters = sorted(clusters, key=cluster_key)
        seat_counter = 1

        for cluster in sorted_clusters:
            if len(cluster) < min_votes:
                continue

            # Compute median box coordinates to reject outline outliers
            xs1 = sorted([b[0] for b in cluster])
            ys1 = sorted([b[1] for b in cluster])
            xs2 = sorted([b[2] for b in cluster])
            ys2 = sorted([b[3] for b in cluster])

            median_box = [
                xs1[len(xs1) // 2],
                ys1[len(ys1) // 2],
                xs2[len(xs2) // 2],
                ys2[len(ys2) // 2]
            ]

            stable_seats.append(SeatDefinition(
                seat_id=str(uuid.uuid4()),
                seat_label=f"Seat {seat_counter}",
                x1=median_box[0],
                y1=median_box[1],
                x2=median_box[2],
                y2=median_box[3],
                track_id=0
            ))
            seat_counter += 1

        logger.info(f"ChairDetector: Found {len(stable_seats)} stable physical chairs.")
        return stable_seats

    def _iou(self, a: List[int], b: List[int]) -> float:
        """Compute Intersection over Union of two boxes."""
        ix1 = max(a[0], b[0]); iy1 = max(a[1], b[1])
        ix2 = min(a[2], b[2]); iy2 = min(a[3], b[3])
        if ix2 <= ix1 or iy2 <= iy1:
            return 0.0
        inter = (ix2 - ix1) * (iy2 - iy1)
        area_a = (a[2] - a[0]) * (a[3] - a[1])
        area_b = (b[2] - b[0]) * (b[3] - b[1])
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0


class SeatOccupancyProcessor:
    """
    Evaluates occupancy on predefined, frozen seat bounding boxes.
    Does NOT detect or track chairs during playback, only detects people.
    """

    def __init__(
        self,
        model_path: str = "yolov8n-pose.pt",
        containment_threshold: float = 0.35,
        aspect_ratio_threshold: float = 0.65,
    ) -> None:
        self.pose_model = get_yolo_model(model_path)
        self.containment_threshold = containment_threshold
        self.aspect_ratio_threshold = aspect_ratio_threshold
        
        # Stateful state machine tracking
        self.seat_stable_states: Dict[str, OccupancyStatus] = {}
        self.seat_occupied_counters: Dict[str, int] = {}
        self.seat_vacant_counters: Dict[str, int] = {}
        self.seat_assigned_track_id: Dict[str, Optional[int]] = {}
        self.latest_seat_person_info: Dict[str, Tuple[float, Optional[List[float]]]] = {}
        
        logger.info("SeatOccupancyProcessor: Model loaded.")

    def detect_occupancy(
        self,
        frame: np.ndarray,
        seats: List[SeatDefinition],
    ) -> Dict[str, Tuple[OccupancyStatus, float, Optional[List[float]]]]:
        """Detect people, track them across frames, and run seat occupancy state transitions."""
        # 1. Initialize tracking structures for any new seats
        for s in seats:
            if s.seat_id not in self.seat_stable_states:
                self.seat_stable_states[s.seat_id] = OccupancyStatus.VACANT
                self.seat_occupied_counters[s.seat_id] = 0
                self.seat_vacant_counters[s.seat_id] = 0
                self.seat_assigned_track_id[s.seat_id] = None
                self.latest_seat_person_info[s.seat_id] = (0.0, None)

        # 2. Run pose model with tracking enabled
        results = None
        try:
            results = self.pose_model.track(frame, persist=True, classes=[0], verbose=False, conf=0.3)
        except Exception as e:
            # Fall back to regular detection if tracker is not supported or errors out
            logger.warning(f"YOLO track failed, falling back to detect: {e}")
            try:
                results = self.pose_model(frame, classes=[0], verbose=False, conf=0.3)
            except Exception:
                pass

        detected_persons: List[Dict[str, Any]] = []
        if results and len(results) > 0:
            r = results[0]
            kps = getattr(r, "keypoints", None)
            box_ids = getattr(r.boxes, "id", None)
            for i, box in enumerate(r.boxes):
                xyxy = box.xyxy[0].cpu().numpy().tolist()
                conf = float(box.conf[0].cpu().item())
                track_id = int(box_ids[i].item()) if box_ids is not None else None
                kp = kps[i] if kps is not None and len(kps) > i else None
                detected_persons.append({
                    "box": xyxy,
                    "conf": conf,
                    "track_id": track_id,
                    "keypoints": kp
                })

        # 3. Evaluate state machine transitions for each seat
        # Hysteresis parameters
        OCCUPIED_CONSECUTIVE_FRAMES = 15
        VACANT_CONSECUTIVE_FRAMES = 10

        seat_results: Dict[str, Tuple[OccupancyStatus, float, Optional[List[float]]]] = {}

        for seat in seats:
            sx1, sy1, sx2, sy2 = seat.x1, seat.y1, seat.x2, seat.y2
            seat_box = [float(sx1), float(sy1), float(sx2), float(sy2)]

            current_stable = self.seat_stable_states[seat.seat_id]
            is_vacant_evidence = True
            best_sitting_person = None
            best_overlap = 0.0

            # Step A: If currently occupied and assigned to a tracked person, check their state
            assigned_tid = self.seat_assigned_track_id[seat.seat_id]
            if current_stable == OccupancyStatus.OCCUPIED and assigned_tid is not None:
                # Find matching tracked person in this frame
                tracked_p = next((p for p in detected_persons if p["track_id"] == assigned_tid), None)
                if tracked_p:
                    overlap = self._intersection_over_seat(tracked_p["box"], seat_box)
                    is_sitting = self._is_sitting(tracked_p["box"], tracked_p["keypoints"], seat_box)
                    
                    # Tracked person has not stood up or left the seat region
                    if overlap > self.containment_threshold and is_sitting:
                        is_vacant_evidence = False
                        best_sitting_person = tracked_p
                        best_overlap = overlap

            # Step B: Fallback to general general detection if no vacancy evidence or no track ID was assigned
            if is_vacant_evidence:
                for p in detected_persons:
                    overlap = self._intersection_over_seat(p["box"], seat_box)
                    is_sitting = self._is_sitting(p["box"], p["keypoints"], seat_box)
                    if overlap > self.containment_threshold and is_sitting:
                        is_vacant_evidence = False
                        if overlap > best_overlap:
                            best_sitting_person = p
                            best_overlap = overlap

            # Step C: Apply hysteresis state transition logic
            if current_stable == OccupancyStatus.VACANT:
                if not is_vacant_evidence:
                    self.seat_occupied_counters[seat.seat_id] += 1
                    self.seat_vacant_counters[seat.seat_id] = 0
                    if self.seat_occupied_counters[seat.seat_id] >= OCCUPIED_CONSECUTIVE_FRAMES:
                        self.seat_stable_states[seat.seat_id] = OccupancyStatus.OCCUPIED
                        self.seat_assigned_track_id[seat.seat_id] = best_sitting_person["track_id"]
                        self.latest_seat_person_info[seat.seat_id] = (best_sitting_person["conf"], best_sitting_person["box"])
                else:
                    self.seat_occupied_counters[seat.seat_id] = 0
                    self.seat_vacant_counters[seat.seat_id] += 1
            else:  # Occupied state
                if is_vacant_evidence:
                    self.seat_vacant_counters[seat.seat_id] += 1
                    self.seat_occupied_counters[seat.seat_id] = 0
                    if self.seat_vacant_counters[seat.seat_id] >= VACANT_CONSECUTIVE_FRAMES:
                        self.seat_stable_states[seat.seat_id] = OccupancyStatus.VACANT
                        self.seat_assigned_track_id[seat.seat_id] = None
                        self.latest_seat_person_info[seat.seat_id] = (0.0, None)
                else:
                    self.seat_vacant_counters[seat.seat_id] = 0
                    self.seat_occupied_counters[seat.seat_id] += 1
                    # Keep track ID and bounding box updated
                    self.seat_assigned_track_id[seat.seat_id] = best_sitting_person["track_id"]
                    self.latest_seat_person_info[seat.seat_id] = (best_sitting_person["conf"], best_sitting_person["box"])

            # Save stable state mapping for return
            stable_status = self.seat_stable_states[seat.seat_id]
            conf, bbox = self.latest_seat_person_info[seat.seat_id]
            seat_results[seat.seat_id] = (stable_status, conf, bbox)

        return seat_results

    def draw_overlays(
        self,
        frame: np.ndarray,
        seats: List[SeatDefinition],
        results: Dict[str, Tuple[OccupancyStatus, float, Optional[List[float]]]],
    ) -> np.ndarray:
        """Draw bounding boxes, labels, and status colors on the frame."""
        import cv2

        annotated = frame

        for seat in seats:
            sx1, sy1, sx2, sy2 = seat.x1, seat.y1, seat.x2, seat.y2
            status, conf, person_box = results.get(seat.seat_id, (OccupancyStatus.VACANT, 0.0, None))

            # Draw person box
            if status == OccupancyStatus.OCCUPIED and person_box:
                px1, py1, px2, py2 = map(int, person_box)
                cv2.rectangle(annotated, (px1, py1), (px2, py2), (0, 165, 255), 2)  # Orange

            # Draw seat box
            color = (255, 144, 30) if status == OccupancyStatus.OCCUPIED else (2, 204, 88) # Dodger Blue vs Feather Green
            cv2.rectangle(annotated, (sx1, sy1), (sx2, sy2), color, 2)

            # Draw seat label text
            label = seat.seat_label
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.45
            thickness = 1
            (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)
            lx1, ly1 = sx1, max(0, sy1 - th - 6)
            cv2.rectangle(annotated, (lx1, ly1), (lx1 + tw + 6, sy1), color, -1)
            cv2.putText(annotated, label, (lx1 + 3, sy1 - 3), font, font_scale, (255, 255, 255), thickness)

        return annotated

    def process_frame(
        self,
        frame: np.ndarray,
        seats: List[SeatDefinition],
    ) -> Tuple[Dict[str, Tuple[OccupancyStatus, float, Optional[List[float]]]], np.ndarray]:
        """Backward-compatible process method."""
        results = self.detect_occupancy(frame, seats)
        annotated = self.draw_overlays(frame, seats, results)
        return results, annotated

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
        """Check if person is in sitting posture, using pose landmarks and fallback heuristics."""
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
                    
                    # 1. Hips and knees are visible
                    if (has_l_hip or has_r_hip) and (has_l_knee or has_r_knee):
                        has_pose = True
                        hip_y = 0.0
                        hips_count = 0
                        if has_l_hip:
                            hip_y += l_hip[1]
                            hips_count += 1
                        if has_r_hip:
                            hip_y += r_hip[1]
                            hips_count += 1
                        hip_y /= hips_count

                        knee_y = 0.0
                        knees_count = 0
                        if has_l_knee:
                            knee_y += l_knee[1]
                            knees_count += 1
                        if has_r_knee:
                            knee_y += r_knee[1]
                            knees_count += 1
                        knee_y /= knees_count

                        # Normalised vertical distance: vertical distance between hip and knee relative to bbox height
                        norm_dy = abs(knee_y - hip_y) / (h + 1e-5)
                        if norm_dy < 0.35:
                            return True

                        # Horizontal thigh check (low slope dy/dx)
                        for hip, knee, has_h, has_k in [(l_hip, l_knee, has_l_hip, has_l_knee), (r_hip, r_knee, has_r_hip, has_r_knee)]:
                            if has_h and has_k:
                                dy = abs(knee[1] - hip[1])
                                dx = abs(knee[0] - hip[0]) + 1e-5
                                if dy / dx < 1.0:
                                    return True
            except Exception as e:
                logger.warning(f"Error in pose keypoint evaluation: {e}")

        # 2. Fallback heuristics when knees are occluded or pose keypoint verification fails
        if not has_pose and seat_box is not None:
            sx1, sy1, sx2, sy2 = seat_box
            sh = sy2 - sy1
            
            # Midpoint of person's vertical span
            py_mid = (py1 + py2) / 2.0
            
            # Check if person's bottom does not extend too far below the seat bottom (which would indicate standing)
            py_bottom_ok = py2 <= sy2 + sh * 0.6
            
            # Check if the vertical centroid of the person lies close to the seat level
            py_centroid_ok = (sy1 - sh * 0.3) <= py_mid <= (sy2 + sh * 0.3)
            
            # Squarer/wider aspect ratio for sitting posture
            aspect_ok = aspect >= self.aspect_ratio_threshold - 0.1  # slightly lower threshold (e.g. 0.55) to be permissive but selective
            
            if py_bottom_ok and py_centroid_ok and aspect_ok:
                return True

        # Generic default fallback using aspect ratio alone if seat_box is not available
        return aspect >= self.aspect_ratio_threshold
