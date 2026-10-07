"""Tests for time-weighted analytics, session summaries and the report CV logic.

None of these need YOLO weights: the occupancy processor is exercised with
synthetic person detections.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.analytics.intervals import (
    Interval,
    accumulate_by_key,
    bucket_timeline,
    build_intervals,
    hour_of_day_key,
    peak_window,
    seat_stats,
)
from app.analytics.session_summary import compute_session_summary
from app.cv.processor import (
    SeatDefinition,
    SeatOccupancyProcessor,
    _Cluster,
    adaptive_cluster,
    assign_owner,
    passes_geometry_gate,
    post_cluster_nms,
    row_axis,
    torso_point,
)
from app.models.occupancy_event import OccupancyStatus
from app.services.insights import build_insights


# ── Intervals ────────────────────────────────────────────────────────────────


def test_build_intervals_merges_repeats_and_uses_initial_state():
    tr = [(10.0, "OCCUPIED"), (20.0, "OCCUPIED"), (30.0, "VACANT")]
    iv = build_intervals(tr, 0.0, 40.0, initial_status="VACANT")
    assert iv == [
        Interval(0.0, 10.0, "VACANT"),
        Interval(10.0, 30.0, "OCCUPIED"),
        Interval(30.0, 40.0, "VACANT"),
    ]


def test_build_intervals_unknown_before_first_observation():
    iv = build_intervals([(5.0, "VACANT")], 0.0, 10.0)
    assert iv[0] == Interval(0.0, 5.0, "UNKNOWN")


def test_seat_stats_are_time_weighted_not_event_counts():
    # Many short vacant blips must not dilute one long occupied stretch.
    iv = [
        Interval(0, 3600, "OCCUPIED"),
        Interval(3600, 3610, "VACANT"),
        Interval(3610, 3620, "OCCUPIED"),
        Interval(3620, 3630, "VACANT"),
        Interval(3630, 7200, "UNKNOWN"),
    ]
    st = seat_stats(iv)
    assert st["occupied_s"] == 3610
    assert st["vacant_s"] == 20
    assert st["observed_s"] == 3630
    assert st["utilization_pct"] == pytest.approx(99.4, abs=0.1)
    assert st["sessions"] == 2
    assert st["longest_session_s"] == 3600
    assert st["current_status"] == "UNKNOWN"


def test_bucket_timeline_ignores_unknown_time():
    seats = {
        "a": [Interval(0, 60, "OCCUPIED"), Interval(60, 120, "UNKNOWN")],
        "b": [Interval(0, 120, "VACANT")],
    }
    tl = bucket_timeline(seats, 0, 120, 60)
    assert tl[0]["occupancy_pct"] == 50.0
    assert tl[0]["observed"] == 2.0
    assert tl[1]["occupancy_pct"] == 0.0
    assert tl[1]["observed"] == 1.0


def test_hour_of_day_split_respects_timezone():
    # 23:30–00:30 UTC seen from UTC+05:30 is 05:00–06:00 local.
    iv = [Interval(23.5 * 3600, 24.5 * 3600, "OCCUPIED")]
    acc = accumulate_by_key(iv, hour_of_day_key(5.5 * 3600))
    assert set(acc) == {5}
    assert acc[5] == (3600.0, 3600.0)


def test_peak_window_finds_longest_run_near_peak():
    tl = [{"t": i * 10.0, "occupied": v, "observed": 4.0} for i, v in enumerate([0, 1, 4, 4, 3.5, 1, 4])]
    w = peak_window(tl, 10.0)
    assert w["start"] == 20.0 and w["end"] == 50.0


# ── Session summary ──────────────────────────────────────────────────────────


def test_session_summary_from_transitions():
    seats = [{"seat_id": "s1", "label": "S01"}, {"seat_id": "s2", "label": "S02"}]
    transitions = [
        ("s1", "VACANT", 0.0), ("s2", "VACANT", 0.0),
        ("s1", "OCCUPIED", 10.0), ("s2", "OCCUPIED", 20.0),
        ("s1", "VACANT", 40.0),
    ]
    samples = [(0.0, 0), (10.0, 1), (20.0, 2), (40.0, 1), (60.0, 1)]
    s = compute_session_summary(seats, transitions, samples, 60.0)
    assert s["seat_count"] == 2
    assert s["peak_occupied"] == 2 and s["peak_at_s"] == 20.0
    assert s["total_occupied_s"] == pytest.approx(70.0)
    assert s["avg_occupancy_pct"] == pytest.approx(58.3, abs=0.1)
    assert s["most_utilized"]["label"] == "S02"
    assert s["state_changes"] == 3
    assert s["occupied_at_end"] == 1


# ── Calibration geometry ─────────────────────────────────────────────────────


def test_geometry_gate_rejects_tiny_and_giant_boxes():
    assert passes_geometry_gate([100, 100, 200, 220], 1920, 1080)
    assert not passes_geometry_gate([0, 0, 10, 10], 1920, 1080)
    assert not passes_geometry_gate([0, 0, 1500, 900], 1920, 1080)


def test_adaptive_cluster_scales_with_box_size():
    dets = [(1, [100, 100, 200, 200], 0.9), (2, [130, 120, 230, 220], 0.8), (3, [400, 100, 440, 140], 0.7)]
    clusters = adaptive_cluster(dets)
    assert len(clusters) == 2
    assert sorted(len(c.frames) for c in clusters) == [1, 2]


def test_post_cluster_nms_collapses_nested_duplicates():
    a, b = _Cluster(), _Cluster()
    a.add([494, 735, 701, 883], 0.81, 1)
    b.add([493, 735, 716, 1065], 0.46, 1)
    kept, suppressed = post_cluster_nms([a, b], 1920, 1080)
    assert suppressed == 1 and kept == [a]


# ── Ownership, torso point, velocity gate ────────────────────────────────────


def _seat(sid, x1, y1, x2, y2):
    return SeatDefinition(seat_id=sid, seat_label=sid.upper(), x1=x1, y1=y1, x2=x2, y2=y2)


ROW = [_seat("s1", 100, 400, 200, 500), _seat("s2", 220, 400, 320, 500)]


def test_row_axis_detects_horizontal_row():
    assert row_axis(ROW) == "x"


def test_one_torso_credits_exactly_one_seat():
    # A point between two adjacent seats still has a single owner.
    owner = assign_owner((212.0, 450.0), ROW, "x")
    assert owner is not None and owner.seat_id == "s2"


def test_cross_axis_check_rejects_people_in_the_aisle_behind():
    assert assign_owner((150.0, 250.0), ROW, "x") is None


def test_torso_point_is_biased_towards_hips():
    kp = np.zeros((17, 2))
    kp[5] = kp[6] = (150, 300)   # shoulders
    kp[11] = kp[12] = (150, 400)  # hips
    (x, y), method = torso_point([100, 250, 200, 520], kp, None, 0.7)
    assert method == "torso" and x == 150 and y == pytest.approx(370)


def _person(track_id, x, y):
    # A wide, short box: the box-based posture fallback treats it as seated.
    return {"box": [x - 60, y - 70, x + 60, y + 40], "conf": 0.9, "track_id": track_id,
            "keypoints": None, "kp_xy": None, "kp_conf": None}


def _processor(**kw):
    return SeatOccupancyProcessor(load_model=False, occ_frames=3, clear_frames=2, **kw)


def test_hysteresis_requires_consecutive_evidence():
    p = _processor()
    for i in range(2):
        r = p.evaluate_report([_person(1, 150, 430)], ROW, 1280, 720)
        assert r["s1"][0] == OccupancyStatus.VACANT
    r = p.evaluate_report([_person(1, 150, 430)], ROW, 1280, 720)
    assert r["s1"][0] == OccupancyStatus.OCCUPIED
    assert r["s2"][0] == OccupancyStatus.VACANT
    for _ in range(2):
        r = p.evaluate_report([], ROW, 1280, 720)
    assert r["s1"][0] == OccupancyStatus.VACANT


def test_velocity_gate_ignores_walking_people():
    p = _processor()
    xs = [100, 150, 200, 250, 300, 350]  # 50 px per reading > 32 px gate at 720p
    for x in xs:
        r = p.evaluate_report([_person(7, x, 430)], ROW, 1280, 720)
    assert all(v[0] == OccupancyStatus.VACANT for v in r.values())
    assert p.last_people[-1]["walking"] is True


# ── Insights ─────────────────────────────────────────────────────────────────


def _analytics(seats, startups=None, hourly=None):
    occ = sum(s["occupied_duration_s"] for s in seats)
    obs = sum(s["observed_duration_s"] for s in seats)
    return {
        "kpi": {
            "observed_seat_hours": obs / 3600, "occupied_seat_hours": occ / 3600,
            "avg_occupancy_pct": occ / obs * 100 if obs else None, "total_seats": len(seats),
            "current_occupancy_pct": None, "occupied_seats": 0, "observed_now": 0,
        },
        "seat_stats": seats,
        "startup_stats": startups or [],
        "hourly": hourly or [{"hour": h, "occupancy_pct": None, "observed_seat_hours": 0} for h in range(24)],
        "peak": {"window": None, "highest_occupancy_pct": None},
        "sources": {}, "window": {},
    }


def _row(label, util, observed=7200, startup=None, sessions=3):
    return {
        "seat_label": label, "utilization_pct": util, "observed_duration_s": observed,
        "occupied_duration_s": observed * util / 100, "sessions": sessions,
        "avg_session_s": observed * util / 100 / max(1, sessions), "longest_session_s": 600,
        "startup_id": startup, "current_status": "VACANT",
    }


def test_insights_need_enough_data():
    out = build_insights(_analytics([_row("S01", 50, observed=60)]))
    assert out["coverage"]["enough_data"] is False
    assert out["recommendations"] == []


def test_insights_flag_underused_seats_and_overallocated_team():
    seats = [_row("S01", 5, startup="t1"), _row("S02", 10, startup="t1"), _row("S03", 70)]
    team = [{"startup_id": "t1", "name": "Team One", "assigned_seats": 2, "utilization_pct": 7.5,
             "peak_concurrent": 1.0, "at_capacity_pct": 0.0}]
    out = build_insights(_analytics(seats, team))
    ids = {r["id"] for r in out["recommendations"]}
    assert "underutilized-seats" in ids
    assert "reduce-t1" not in ids  # peak (1) + spare would equal assigned (2): nothing to reduce
    assert out["health"]["score"] is not None
