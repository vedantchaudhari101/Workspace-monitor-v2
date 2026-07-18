"""Audit log model for system-wide action tracking.

Provides an immutable audit trail of all significant actions
performed in the system. Audit log entries are append-only
(no updates) and only use the UUIDMixin with a manual created_at
column — no updated_at is needed.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDMixin
from app.models.user import User


class AuditLog(UUIDMixin, Base):
    """Immutable audit trail entry for system actions.

    Records every significant action in the system including who
    performed it, what entity was affected, and contextual details.
    Entries are append-only — they are never updated or deleted
    in normal operation. Only uses UUIDMixin (no TimestampMixin)
    since audit logs only need a created_at timestamp.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped[User | None] = relationship(
        "User", back_populates="audit_logs", lazy="joined"
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id!r}, action={self.action!r}, "
            f"user_id={self.user_id!r}, entity_type={self.entity_type!r}, "
            f"entity_id={self.entity_id!r})>"
        )
