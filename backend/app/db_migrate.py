"""Apply Alembic migrations programmatically (used on startup and by the seed script).

Handles three database states:

* empty database           → ``upgrade head`` builds the full schema
* pre-Alembic database     → created by ``create_all`` before migrations existed;
                             stamped at the matching revision, then upgraded
* migrated database        → ``upgrade head`` applies anything new
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic_config():
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url_sync)
    cfg.attributes["url_from_caller"] = True
    return cfg


def run_migrations() -> None:
    """Bring the configured database to the latest schema revision."""
    from alembic import command

    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    try:
        tables = set(inspect(engine).get_table_names())
        columns = (
            {c["name"] for c in inspect(engine).get_columns("occupancy_events")}
            if "occupancy_events" in tables
            else set()
        )
    finally:
        engine.dispose()

    cfg = _alembic_config()
    if "alembic_version" not in tables and "buildings" in tables:
        # Schema was created with create_all() — record where it stands.
        if "analysis_sessions" in tables and "source" in columns:
            logger.info("Stamping existing schema at head")
            command.stamp(cfg, "head")
            return
        logger.info("Stamping pre-migration schema at 0001")
        command.stamp(cfg, "0001")

    command.upgrade(cfg, "head")
    logger.info("Database schema is up to date")
