"""Workspace insights and rule-based recommendations.

Everything here is deterministic and computed from the measured analytics
returned by :func:`app.services.seat_history.compute_analytics`. Each item
carries the rule that produced it and the evidence behind it, so the UI can
show *why* — nothing is generated text and nothing is presented as ML.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

MIN_OBSERVED_SEAT_S = 300  # 5 seat-minutes before we draw conclusions
SHORT_SESSION_S = 60
LONG_SESSION_S = 4 * 3600


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _hour_label(h: int) -> str:
    return f"{h:02d}:00"


def _fmt_minutes(seconds: Optional[float]) -> str:
    if not seconds:
        return "0 s"
    if seconds < 60:
        return f"{int(round(seconds))} s"
    m = int(round(seconds / 60))
    if m < 60:
        return f"{m} min"
    return f"{m // 60} h {m % 60:02d} min"


def _hour_runs(hours: List[Dict[str, Any]], predicate) -> List[List[int]]:
    runs: List[List[int]] = []
    cur: List[int] = []
    for h in hours:
        if h["occupancy_pct"] is not None and predicate(h):
            cur.append(h["hour"])
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return runs


def build_insights(analytics: Dict[str, Any]) -> Dict[str, Any]:
    kpi = analytics["kpi"]
    seats = analytics["seat_stats"]
    startups = analytics["startup_stats"]
    hourly = analytics["hourly"]
    peak = analytics["peak"]
    observed_s = kpi["observed_seat_hours"] * 3600.0

    observed_seats = [s for s in seats if (s["observed_duration_s"] or 0) > 0]
    enough = observed_s >= MIN_OBSERVED_SEAT_S and observed_seats

    coverage = {
        "observed_seat_hours": kpi["observed_seat_hours"],
        "observed_seats": len(observed_seats),
        "total_seats": kpi["total_seats"],
        "sessions": sum(s["sessions"] or 0 for s in seats),
        "enough_data": bool(enough),
        "min_observed_seat_minutes": MIN_OBSERVED_SEAT_S // 60,
    }
    if not enough:
        return {
            "coverage": coverage,
            "health": None,
            "measured": [],
            "recommendations": [],
            "warnings": [],
            "unusual": [],
            "sources": analytics["sources"],
            "window": analytics["window"],
        }

    # ── Health scores (formulas are returned with the numbers) ─────────────
    avg = kpi["avg_occupancy_pct"] or 0.0
    utilization_score = round(_clamp(100.0 - abs(avg - 70.0) * (100.0 / 70.0)), 1)
    balanced = [s for s in observed_seats if 20.0 <= (s["utilization_pct"] or 0.0) <= 90.0]
    balance_score = round(len(balanced) / len(observed_seats) * 100.0, 1)
    sessions_total = sum(s["sessions"] or 0 for s in observed_seats)
    short = []
    for s in observed_seats:
        # Only judge flicker on seats watched long enough for a real session to fit.
        if (
            s["sessions"]
            and s["avg_session_s"] is not None
            and s["avg_session_s"] < SHORT_SESSION_S
            and (s["observed_duration_s"] or 0) >= 10 * SHORT_SESSION_S
        ):
            short.append(s)
    short_sessions = sum(s["sessions"] for s in short)
    stability_score = round(_clamp(100.0 - (short_sessions / sessions_total * 100.0 if sessions_total else 0.0)), 1)
    health = round(0.5 * utilization_score + 0.3 * balance_score + 0.2 * stability_score)

    health_block = {
        "score": health,
        "components": [
            {"key": "utilization", "label": "Utilization", "score": utilization_score,
             "explain": f"Average utilization {avg:.1f}% against a 70% target. 100 at 70%, falling linearly to 0 at 0% or 140%."},
            {"key": "balance", "label": "Balance", "score": balance_score,
             "explain": f"{len(balanced)} of {len(observed_seats)} observed seats sit between 20% and 90% utilization."},
            {"key": "stability", "label": "Stability", "score": stability_score,
             "explain": f"{short_sessions} of {sessions_total} sessions belong to seats averaging under {SHORT_SESSION_S}s per session, which usually means detection flicker."},
        ],
        "formula": "0.5 × utilization + 0.3 × balance + 0.2 × stability",
    }

    # ── Measured insights (facts, no advice) ───────────────────────────────
    measured: List[Dict[str, Any]] = []
    window = peak.get("window")
    if window:
        measured.append({
            "id": "peak-window",
            "title": "Peak occupancy window",
            "value_start": window["start"],
            "value_end": window["end"],
            "detail": f"Occupancy stayed within 15% of its peak (about {window['avg_occupied']:.1f} seats, {window['occupancy_pct'] or 0:.0f}% of observed seats).",
        })
    observed_hours = [h for h in hourly if h["occupancy_pct"] is not None]
    if len(observed_hours) >= 2:
        hi = max(observed_hours, key=lambda h: h["occupancy_pct"])
        lo = min(observed_hours, key=lambda h: h["occupancy_pct"])
        measured.append({
            "id": "busiest-hour", "title": "Busiest hour",
            "detail": f"{_hour_label(hi['hour'])}–{_hour_label((hi['hour'] + 1) % 24)} averaged {hi['occupancy_pct']:.0f}% occupancy.",
        })
        measured.append({
            "id": "quietest-hour", "title": "Quietest hour",
            "detail": f"{_hour_label(lo['hour'])}–{_hour_label((lo['hour'] + 1) % 24)} averaged {lo['occupancy_pct']:.0f}% occupancy.",
        })
    ranked = sorted(observed_seats, key=lambda s: (s["utilization_pct"] or 0.0), reverse=True)
    if ranked:
        top = ranked[0]
        measured.append({
            "id": "most-used-seat", "title": "Most used seat",
            "detail": f"{top['seat_label']} was occupied {top['utilization_pct']:.0f}% of observed time ({_fmt_minutes(top['occupied_duration_s'])}, {top['sessions']} session{'' if top['sessions'] == 1 else 's'}).",
        })
    measured.append({
        "id": "unused-capacity", "title": "Unused capacity",
        "detail": f"{100 - avg:.0f}% of observed seat-time was vacant ({_fmt_minutes(observed_s - kpi['occupied_seat_hours'] * 3600)} of {_fmt_minutes(observed_s)} seat-time).",
    })

    # ── Rule-based recommendations ─────────────────────────────────────────
    recs: List[Dict[str, Any]] = []

    under = [s for s in observed_seats if (s["utilization_pct"] or 0.0) < 20.0 and (s["observed_duration_s"] or 0) >= 1800]
    if under:
        recs.append({
            "id": "underutilized-seats",
            "rule": "Seat utilization below 20% with at least 30 minutes observed",
            "severity": "medium" if len(under) < max(3, len(observed_seats) // 3) else "high",
            "title": f"{len(under)} seat{'s' if len(under) != 1 else ''} rarely used",
            "detail": "These seats were vacant more than 80% of the time they were observed. Consider consolidating them or offering them to teams that run out of space.",
            "evidence": [{"label": s["seat_label"], "value": f"{s['utilization_pct']:.0f}%"} for s in under[:12]],
        })

    for st in startups:
        if st["utilization_pct"] is None or st["assigned_seats"] < 2:
            continue
        needed = max(1, math.ceil(st["peak_concurrent"]))
        if st["utilization_pct"] < 40.0 and needed + 1 < st["assigned_seats"]:
            recs.append({
                "id": f"reduce-{st['startup_id']}",
                "rule": "Team utilization below 40% and observed peak below assigned seats",
                "severity": "medium",
                "title": f"{st['name']} uses fewer seats than assigned",
                "detail": f"{st['name']} averaged {st['utilization_pct']:.0f}% across {st['assigned_seats']} assigned seats and never used more than {needed} at once. {needed + 1} seats would still cover its observed peak with one to spare.",
                "evidence": [
                    {"label": "Assigned", "value": str(st["assigned_seats"])},
                    {"label": "Peak at once", "value": str(needed)},
                    {"label": "Utilization", "value": f"{st['utilization_pct']:.0f}%"},
                ],
            })
        if st["at_capacity_pct"] is not None and st["at_capacity_pct"] >= 30.0:
            recs.append({
                "id": f"expand-{st['startup_id']}",
                "rule": "All assigned seats occupied for at least 30% of observed time",
                "severity": "high" if st["at_capacity_pct"] >= 60 else "medium",
                "title": f"{st['name']} is often at full capacity",
                "detail": f"Every one of {st['name']}'s {st['assigned_seats']} seats was in use for {st['at_capacity_pct']:.0f}% of the observed time. Adding a seat would relieve contention.",
                "evidence": [
                    {"label": "Assigned", "value": str(st["assigned_seats"])},
                    {"label": "Time at capacity", "value": f"{st['at_capacity_pct']:.0f}%"},
                ],
            })

    unassigned_busy = [s for s in observed_seats if not s["startup_id"] and (s["utilization_pct"] or 0.0) >= 50.0]
    if unassigned_busy and startups:
        recs.append({
            "id": "assign-busy-seats",
            "rule": "Unassigned seat occupied at least 50% of observed time",
            "severity": "low",
            "title": f"{len(unassigned_busy)} unassigned seat{'s are' if len(unassigned_busy) != 1 else ' is'} in regular use",
            "detail": "Assigning these seats to the teams using them keeps allocation reports accurate.",
            "evidence": [{"label": s["seat_label"], "value": f"{s['utilization_pct']:.0f}%"} for s in unassigned_busy[:12]],
        })

    low_runs = _hour_runs(hourly, lambda h: h["occupancy_pct"] < 30.0 and h["observed_seat_hours"] > 0)
    if low_runs and avg >= 30.0:
        run = max(low_runs, key=len)
        if len(run) >= 2:
            pct = [h["occupancy_pct"] for h in hourly if h["hour"] in run]
            recs.append({
                "id": "quiet-hours",
                "rule": "Two or more consecutive hours below 30% while the daily average is at least 30%",
                "severity": "low",
                "title": f"Quiet stretch {_hour_label(run[0])}–{_hour_label((run[-1] + 1) % 24)}",
                "detail": f"Occupancy averaged {sum(pct) / len(pct):.0f}% in these hours. Shared bookings, cleaning or maintenance fit here with the least disruption.",
                "evidence": [{"label": _hour_label(h), "value": f"{p:.0f}%"} for h, p in zip(run, pct)],
            })

    if peak.get("highest_occupancy_pct") is not None and peak["highest_occupancy_pct"] >= 90.0:
        recs.append({
            "id": "peak-capacity",
            "rule": "Workspace occupancy reached 90% or more",
            "severity": "high",
            "title": "Little spare capacity at peak",
            "detail": f"Occupancy reached {peak['highest_occupancy_pct']:.0f}% of observed seats. New members at peak time may not find a free seat.",
            "evidence": [{"label": "Peak", "value": f"{peak['highest_occupancy_pct']:.0f}%"}],
            "at": peak.get("peak_timestamp"),
        })

    # ── Warnings and unusual activity ───────────────────────────────────────
    warnings: List[Dict[str, Any]] = []
    if kpi["current_occupancy_pct"] is not None and kpi["current_occupancy_pct"] >= 90.0:
        warnings.append({"id": "capacity-now", "title": "Near capacity now",
                         "detail": f"{kpi['occupied_seats']} of {kpi['observed_now']} observed seats are occupied."})
    unusual: List[Dict[str, Any]] = []
    if short:
        unusual.append({"id": "short-sessions", "title": "Very short sessions",
                        "detail": f"{', '.join(s['seat_label'] for s in short[:8])} average under a minute per session. Check the camera angle or re-run calibration.",
                        "seats": [s["seat_label"] for s in short]})
    long_ = [s for s in observed_seats if (s["longest_session_s"] or 0) >= LONG_SESSION_S]
    if long_:
        unusual.append({"id": "long-sessions", "title": "Unbroken sessions over 4 hours",
                        "detail": f"{', '.join(s['seat_label'] for s in long_[:8])} stayed occupied for over four hours without a break. An object left on a chair can look like a person.",
                        "seats": [s["seat_label"] for s in long_]})

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: severity_rank.get(r["severity"], 3))

    return {
        "coverage": coverage,
        "health": health_block,
        "measured": measured,
        "recommendations": recs,
        "warnings": warnings,
        "unusual": unusual,
        "sources": analytics["sources"],
        "window": analytics["window"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
