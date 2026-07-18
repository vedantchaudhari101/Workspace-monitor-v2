"""Structured Logging Utilities.

Provides JSON-formatted logging for production and human-readable coloured
output for local development.  Call :func:`get_logger` anywhere in the
application to obtain a consistently configured logger.

Usage::

    from app.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Server started", extra={"port": 8000})
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from app.config import get_settings


# ── JSON Formatter ──────────────────────────────────────────────────────────


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects.

    Each emitted line contains at minimum:
    - ``timestamp`` (ISO-8601)
    - ``level``
    - ``name`` (logger name)
    - ``message``

    Any *extra* fields passed via ``extra={...}`` are merged at the top level.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a :class:`~logging.LogRecord` to a JSON string."""
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }

        # Merge caller-supplied extra fields (skip internal LogRecord attrs).
        standard_attrs = logging.LogRecord(
            "", 0, "", 0, "", (), None
        ).__dict__.keys()
        for key, value in record.__dict__.items():
            if key not in standard_attrs and key not in log_entry:
                log_entry[key] = value

        # Include exception info when present.
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


# ── Setup Helpers ───────────────────────────────────────────────────────────

_LOG_CONFIGURED = False


def setup_logging(level: str = "INFO", *, debug: bool = False) -> None:
    """Configure the root logger with an appropriate handler and formatter.

    Parameters
    ----------
    level:
        Standard Python log level name (``DEBUG``, ``INFO``, ``WARNING``, …).
    debug:
        When ``True``, uses a human-readable coloured console format instead
        of JSON.  Typically mirrors ``Settings.DEBUG``.
    """
    global _LOG_CONFIGURED  # noqa: PLW0603
    if _LOG_CONFIGURED:
        return
    _LOG_CONFIGURED = True

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    if debug:
        # Coloured, human-friendly format for local development.
        formatter = logging.Formatter(
            "\033[36m%(asctime)s\033[0m | "
            "\033[1m%(levelname)-8s\033[0m | "
            "%(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        formatter = JsonFormatter()

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Silence overly chatty third-party loggers.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if debug else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.

    Ensures :func:`setup_logging` has been called at least once before
    returning the logger so that handlers are always attached.

    Parameters
    ----------
    name:
        Typically ``__name__`` of the calling module.
    """
    settings = get_settings()
    setup_logging(level=settings.LOG_LEVEL, debug=settings.DEBUG)
    return logging.getLogger(name)


# ── Auto-configure on import ────────────────────────────────────────────────

_settings = get_settings()
setup_logging(level=_settings.LOG_LEVEL, debug=_settings.DEBUG)
