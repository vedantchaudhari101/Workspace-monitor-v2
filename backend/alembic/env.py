"""Alembic Environment Configuration.

Reads the application settings to build the database URL and sets the
SQLAlchemy metadata target so that ``alembic revision --autogenerate``
can diff against the current model state.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── Application imports ─────────────────────────────────────────────────────

from app.config import get_settings
from app.database import Base

# Import all models so they register with Base.metadata.
# This is required for alembic revision --autogenerate to detect tables.
import app.models  # noqa: F401

# ── Alembic Config object ──────────────────────────────────────────────────

config = context.config

# Interpret the alembic.ini logging config.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the sqlalchemy.url from settings (sync driver for Alembic) unless
# the caller (e.g. the startup migration runner) already supplied one.
settings = get_settings()
if not config.attributes.get("url_from_caller"):
    config.set_main_option("sqlalchemy.url", settings.database_url_sync)

# Set target metadata for autogenerate support.
target_metadata = Base.metadata


# ── Offline Migrations ──────────────────────────────────────────────────────


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well.  By skipping the Engine
    creation we don't even need a DBAPI to be available.

    Calls to ``context.execute()`` here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online Migrations ──────────────────────────────────────────────────────


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a
    connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite cannot ALTER columns/constraints in place; batch mode
            # recreates the table transparently.
            render_as_batch=connection.dialect.name == "sqlite",
        )

        with context.begin_transaction():
            context.run_migrations()


# ── Entrypoint ──────────────────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
