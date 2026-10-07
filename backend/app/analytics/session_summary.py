"""Post-analysis summary for one processed video.

Computed once when a session ends, from the transitions the pipeline
observed (in video seconds) and the occupied-seat count sampled at each
inference. Stored in ``analysis_sessions.summary``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from app.analytics.intervals import (
    OCCUPIED,
    build_intervals,
    bucket_timeline,
    peak_window,
    seat_stats,
)

MAX_TIMELINE_POINTS = 240


def compute_session_summary(
    seats: Sequence[Dict[str, str]],
    transitions: Sequence[Tuple[str, str, float]],
    samples: Sequence[Tuple[float, int]],
    duration_s: float,
    start_s: float = 0.0,
) -> Dict:
    """Build the summary.

    Args:
        seats: ``[{"seat_id", "label"}]`` in display order.
        transitions: ``(seat_id, status, video_ts)`` in time order, including
            the initial state each seat was first observed in.
        samples: ``(video_ts, occupied_count)`` per inference.
        duration_s: end of observation in video seconds.
        start_s: start of observation in video seconds.
    """
    seat_count = len(seats)
    end_s = max(duration_s, start_s)

    per_seat: Dict[str, List[Tuple[float, str]]] = {s["seat_id"]: [] for s in seats}
    for seat_id, status, ts in transitions:
        if seat_id in per_seat:
            per_seat[seat_id].append((ts, status))

    seat_intervals = {
        sid: build_intervals(sorted(tr), start_s, end_s) for sid, tr in per_seat.items()
    }

    seat_rows = []
    for s in seats:
        st = seat_stats(seat_intervals[s["seat_id"]])
        seat_rows.append({"seat_id": s["seat_id"], "label": s["label"], **st})

    span = max(0.0, end_s - start_s)
    bucket_s = max(1.0, span / MAX_TIMELINE_POINTS) if span > 0 else 1.0
    timeline = bucket_timeline(seat_intervals, start_s, end_s, bucket_s) if span > 0 else []

    # Peak from raw samples (exact instant), window from the bucketed timeline.
    peak_count = 0
    peak_ts: Optional[float] = None
    for ts, count in samples:
        if count > peak_count:
            peak_count, peak_ts = count, ts

    total_occupied_s = sum(r["occupied_s"] or 0.0 for r in seat_rows)
    total_observed_s = sum(r["observed_s"] or 0.0 for r in seat_rows)
    avg_pct = round(total_occupied_s / total_observed_s * 100.0, 1) if total_observed_s > 0 else None

    ranked = [r for r in seat_rows if r["utilization_pct"] is not None]
    most = max(ranked, key=lambda r: (r["utilization_pct"], r["occupied_s"]), default=None)
    least = min(ranked, key=lambda r: (r["utilization_pct"], r["occupied_s"]), default=None)

    window = peak_window(timeline, bucket_s)
    transitions_count = sum(
        max(0, sum(1 for i in range(1, len(tr)) if tr[i][1] != tr[i - 1][1]))
        for tr in per_seat.values()
    )

    return {
        "seat_count": seat_count,
        "duration_s": round(span, 2),
        "peak_occupied": peak_count,
        "peak_at_s": round(peak_ts, 2) if peak_ts is not None else None,
        "avg_occupancy_pct": avg_pct,
        "total_occupied_s": round(total_occupied_s, 2),
        "most_utilized": {"label": most["label"], "utilization_pct": most["utilization_pct"]} if most and most["occupied_s"] else None,
        "least_utilized": {"label": least["label"], "utilization_pct": least["utilization_pct"]} if least else None,
        "peak_window": window,
        "state_changes": transitions_count,
        "occupied_at_end": sum(1 for r in seat_rows if r["current_status"] == OCCUPIED),
        "timeline_bucket_s": round(bucket_s, 3),
        "timeline": [
            {"t": round(b["t"], 2), "occupied": b["occupied"], "occupancy_pct": b["occupancy_pct"]}
            for b in timeline
        ],
        "seats": seat_rows,
    }
