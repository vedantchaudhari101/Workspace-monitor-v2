"""Centralized Application Configuration.

Uses pydantic-settings to load and validate all configuration from environment
variables and .env files. Every setting has a sensible default for local
development; production values MUST be supplied via environment or .env.

Usage::

    from app.config import get_settings
    settings = get_settings()
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings sourced from environment variables.

    Attributes are grouped by concern: database, auth, computer-vision, and
    general application settings.  Property helpers derive connection strings
    so that they stay consistent with the individual components.
    """

    # ── Database ────────────────────────────────────────────────────────
    USE_SQLITE: bool = Field(default=True, description="Use self-contained SQLite db instead of PostgreSQL")
    POSTGRES_HOST: str = Field(default="localhost", description="PostgreSQL host address")
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL port")
    POSTGRES_USER: str = Field(default="workspace_user", description="PostgreSQL username")
    POSTGRES_PASSWORD: str = Field(default="workspace_pass_dev", description="PostgreSQL password")
    POSTGRES_DB: str = Field(default="workspace_monitor", description="PostgreSQL database name")

    # ── Authentication ──────────────────────────────────────────────────
    SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
        description="Secret key for JWT signing — MUST be changed in production",
    )
    ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30, description="Access token lifetime in minutes"
    )
    OAUTH2_CLIENT_ID: str = Field(default="", description="OAuth2 provider client ID")
    OAUTH2_CLIENT_SECRET: str = Field(default="", description="OAuth2 provider client secret")
    OAUTH2_REDIRECT_URI: str = Field(default="", description="OAuth2 redirect URI")

    # ── Computer Vision ─────────────────────────────────────────────────
    YOLO_MODEL_PATH: str = Field(
        default="yolo26n.pt", description="Path to the YOLO model weights"
    )
    CONFIDENCE_THRESHOLD: float = Field(
        default=0.5, description="Minimum confidence for CV detections"
    )
    FRAME_SKIP_INTERVAL: int = Field(
        default=5, description="Process every Nth frame for efficiency"
    )

    # ── Application ─────────────────────────────────────────────────────
    APP_NAME: str = Field(default="WorkspaceMonitor", description="Application display name")
    APP_VERSION: str = Field(default="1.0.0", description="Semantic version")
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Root log level")
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
        description="Allowed CORS origins",
    )

    # ── Derived Properties ──────────────────────────────────────────────

    @property
    def database_url(self) -> str:
        """Async database URL (used at runtime)."""
        if self.USE_SQLITE:
            return "sqlite+aiosqlite:///workspace_monitor.db"
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def database_url_sync(self) -> str:
        """Synchronous database URL (used by Alembic)."""
        if self.USE_SQLITE:
            return "sqlite:///workspace_monitor.db"
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Pydantic-Settings Config ────────────────────────────────────────

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance.

    Using ``lru_cache`` ensures the .env file is read only once per process
    and the same ``Settings`` object is reused across the application.
    """
    return Settings()
