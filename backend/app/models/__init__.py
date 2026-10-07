"""SQLAlchemy ORM Models.

All models are imported here to ensure they are registered with
Base.metadata before Alembic generates migrations.
"""
from __future__ import annotations

from app.models.base import UUIDMixin, TimestampMixin  # noqa: F401
from app.models.user import User, UserRole  # noqa: F401
from app.models.building import Building  # noqa: F401
from app.models.floor import Floor  # noqa: F401
from app.models.zone import Zone, ZoneType  # noqa: F401
from app.models.seat import Seat  # noqa: F401
from app.models.startup import Startup  # noqa: F401
from app.models.employee import Employee  # noqa: F401
from app.models.seat_allocation import SeatAllocation  # noqa: F401
from app.models.camera import Camera  # noqa: F401
from app.models.analysis_session import AnalysisSession, SessionStatus  # noqa: F401
from app.models.occupancy_event import OccupancyEvent, OccupancyStatus, EventSource  # noqa: F401
from app.models.occupancy_snapshot import OccupancySnapshot, PeriodType  # noqa: F401
from app.models.recommendation import (  # noqa: F401
    Recommendation,
    RecommendationType,
    RecommendationPriority,
    RecommendationStatus,
)
from app.models.audit_log import AuditLog  # noqa: F401

__all__ = [
    "UUIDMixin",
    "TimestampMixin",
    "User",
    "UserRole",
    "Building",
    "Floor",
    "Zone",
    "ZoneType",
    "Seat",
    "Startup",
    "Employee",
    "SeatAllocation",
    "Camera",
    "AnalysisSession",
    "SessionStatus",
    "OccupancyEvent",
    "EventSource",
    "OccupancyStatus",
    "OccupancySnapshot",
    "PeriodType",
    "Recommendation",
    "RecommendationType",
    "RecommendationPriority",
    "RecommendationStatus",
    "AuditLog",
]
