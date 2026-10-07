"""Timestamp helpers.

SQLite returns naive datetimes for ``DateTime(timezone=True)`` columns. All
times are written in UTC, so naive values are UTC and must be serialised
with an explicit offset — otherwise browsers read them as local time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def iso_utc(dt: Optional[datetime]) -> Optional[str]:
    v = as_utc(dt)
    return v.isoformat() if v else None
