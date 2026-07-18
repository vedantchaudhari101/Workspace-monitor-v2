"""User model for system authentication and authorization.

Supports both traditional email/password authentication and OAuth2
provider-based authentication (e.g., Google, GitHub). Users are
assigned roles that control their access level within the platform.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog


class UserRole(str, enum.Enum):
    """Roles controlling user access levels."""

    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    VIEWER = "VIEWER"


class User(UUIDMixin, TimestampMixin, Base):
    """System user for authentication and authorization.

    Supports email/password and OAuth2 authentication flows.
    Each user is assigned a role (ADMIN, MANAGER, VIEWER) that
    determines their permissions within the platform.
    """

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_oauth_provider_oauth_id", "oauth_provider", "oauth_id"),
    )

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        default=UserRole.VIEWER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    oauth_provider: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    oauth_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    audit_logs: Mapped[list[AuditLog]] = relationship(
        "AuditLog", back_populates="user", lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id!r}, email={self.email!r}, "
            f"role={self.role!r}, is_active={self.is_active!r})>"
        )
