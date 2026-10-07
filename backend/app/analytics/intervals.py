"""Time-weighted occupancy maths shared by session summaries and analytics.

The CV pipeline stores *state changes* (and a closing UNKNOWN when a run
ends). Every metric here is derived by turning those changes into intervals
and measuring time, never by counting events. Times are plain floats in
seconds — epoch seconds for wall-clock analytics, video seconds for session
summaries — so the same code serves both.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

OCCUPIED = "OCCUPIED"
VACANT = "VACANT"
UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Interval:
    start: float
    end: float
    status: str

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def build_intervals(
    transitions: Iterable[Tuple[float, str]],
    window_start: float,
    window_end: float,
    initial_status: Optional[str] = None,
) -> List[Interval]:
    """Convert ordered ``(time, status)`` assertions into contiguous intervals.

    ``initial_status`` is the state in force at ``window_start`` (the latest
    assertion before the window), or None when nothing was known yet.
    Consecutive assertions of the same state are merged.
    """
    if window_end <= window_start:
        return []
    current = initial_status or UNKNOWN
    cursor = window_start
    out: List[Interval] = []
    for t, status in transitions:
        if t < window_start:
            current = status
            continue
        if t >= window_end:
            break
        if status == current:
            continue
        if t > cursor:
            out.append(Interval(cursor, t, current))
        cursor = t
        current = status
    out.append(Interval(cursor, window_end, current))
    return [i for i in out if i.duration > 0]


def seat_stats(intervals: Sequence[Interval]) -> Dict[str, Optional[float]]:
    """Occupied/vacant time, sessions and utilization for one seat."""
    occupied = [i for i in intervals if i.status == OCCUPIED]
    occupied_s = sum(i.duration for i in occupied)
    vacant_s = sum(i.duration for i in intervals if i.status == VACANT)
    observed_s = occupied_s + vacant_s
    durations = [i.duration for i in occupied]
    current = intervals[-1] if intervals else None
    return {
        "occupied_s": round(occupied_s, 2),
        "vacant_s": round(vacant_s, 2),
        "observed_s": round(observed_s, 2),
        "utilization_pct": round(occupied_s / observed_s * 100.0, 1) if observed_s > 0 else None,
        "sessions": len(occupied),
        "avg_session_s": round(sum(durations) / len(durations), 2) if durations else None,
        "longest_session_s": round(max(durations), 2) if durations else None,
        "first_occupied": occupied[0].start if occupied else None,
        "last_occupied": occupied[-1].end if occupied else None,
        "current_status": current.status if current else UNKNOWN,
        "current_since": current.start if current else None,
    }


def bucket_timeline(
    seat_intervals: Dict[str, List[Interval]],
    start: float,
    end: float,
    bucket_s: float,
) -> List[Dict[str, float]]:
    """Time-weighted occupancy per bucket across all seats.

    Each bucket reports the average number of occupied seats, the average
    number of observed seats, and occupancy % = occupied / observed.
    Buckets with no observation report ``occupancy_pct = None``.
    """
    if end <= start or bucket_s <= 0:
        return []
    n = max(1, math.ceil((end - start) / bucket_s))
    occ = [0.0] * n
    obs = [0.0] * n
    for intervals in seat_intervals.values():
        for iv in intervals:
            if iv.status == UNKNOWN:
                continue
            a = max(iv.start, start)
            b = min(iv.end, end)
            if b <= a:
                continue
            first = int((a - start) // bucket_s)
            last = min(n - 1, int((b - start - 1e-9) // bucket_s))
            for k in range(first, last + 1):
                bs = start + k * bucket_s
                be = min(end, bs + bucket_s)
                overlap = min(b, be) - max(a, bs)
                if overlap <= 0:
                    continue
                obs[k] += overlap
                if iv.status == OCCUPIED:
                    occ[k] += overlap
    out = []
    for k in range(n):
        bs = start + k * bucket_s
        length = min(end, bs + bucket_s) - bs
        out.append({
            "t": bs,
            "occupied": round(occ[k] / length, 2) if length > 0 else 0.0,
            "observed": round(obs[k] / length, 2) if length > 0 else 0.0,
            "occupancy_pct": round(occ[k] / obs[k] * 100.0, 1) if obs[k] > 0 else None,
        })
    return out


def max_concurrent(seat_intervals: Dict[str, List[Interval]]) -> Tuple[int, Optional[float]]:
    """Exact peak number of simultaneously occupied seats, and when it first happened."""
    edges: List[Tuple[float, int]] = []
    for intervals in seat_intervals.values():
        for iv in intervals:
            if iv.status == OCCUPIED and iv.duration > 0:
                edges.append((iv.start, 1))
                edges.append((iv.end, -1))
    edges.sort(key=lambda e: (e[0], e[1]))  # ends before starts at the same instant
    best, at, cur = 0, None, 0
    for t, d in edges:
        cur += d
        if cur > best:
            best, at = cur, t
    return best, at


def accumulate_by_key(
    intervals: Iterable[Interval],
    key_and_boundary: Callable[[float], Tuple[int, float]],
) -> Dict[int, Tuple[float, float]]:
    """Split intervals at boundaries (e.g. hour of day) → {key: (occupied_s, observed_s)}.

    ``key_and_boundary(t)`` returns the key for time ``t`` and the time at
    which the key next changes.
    """
    acc: Dict[int, List[float]] = {}
    for iv in intervals:
        if iv.status == UNKNOWN:
            continue
        t = iv.start
        while t < iv.end:
            key, boundary = key_and_boundary(t)
            seg_end = min(iv.end, boundary)
            if seg_end <= t:
                break
            slot = acc.setdefault(key, [0.0, 0.0])
            slot[1] += seg_end - t
            if iv.status == OCCUPIED:
                slot[0] += seg_end - t
            t = seg_end
    return {k: (v[0], v[1]) for k, v in acc.items()}


def hour_of_day_key(tz_offset_s: float) -> Callable[[float], Tuple[int, float]]:
    """Key function for local hour-of-day given a UTC offset in seconds."""

    def fn(t: float) -> Tuple[int, float]:
        local = t + tz_offset_s
        hour_start = math.floor(local / 3600.0) * 3600.0
        return int((hour_start // 3600) % 24), hour_start + 3600.0 - tz_offset_s

    return fn


def peak_window(timeline: List[Dict[str, float]], bucket_s: float, threshold: float = 0.85) -> Optional[Dict[str, float]]:
    """Longest contiguous run of buckets at or above ``threshold`` × peak occupancy.

    Returns ``None`` when nothing was ever occupied.
    """
    values = [b["occupied"] for b in timeline]
    if not values or max(values) <= 0:
        return None
    peak = max(values)
    cut = peak * threshold
    best: Tuple[int, int] = (0, -1)
    run_start = None
    for i, v in enumerate(values + [-1.0]):
        if v >= cut and v > 0:
            if run_start is None:
                run_start = i
        elif run_start is not None:
            if (i - 1 - run_start) > (best[1] - best[0]):
                best = (run_start, i - 1)
            run_start = None
    if best[1] < best[0]:
        return None
    s, e = best
    seg = timeline[s:e + 1]
    observed = sum(b["observed"] for b in seg)
    return {
        "start": timeline[s]["t"],
        "end": timeline[e]["t"] + bucket_s,
        "avg_occupied": round(sum(b["occupied"] for b in seg) / len(seg), 2),
        "occupancy_pct": round(sum(b["occupied"] for b in seg) / observed * 100.0, 1) if observed > 0 else None,
    }
