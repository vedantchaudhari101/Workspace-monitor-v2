"""FastAPI Application Factory.

Builds the top-level ASGI application with middleware, routers, and a
health-check endpoint.  The ``create_app`` factory pattern makes it easy to
spin up fresh instances in tests.

Usage (production)::

    uvicorn app.main:app --host 0.0.0.0 --port 8000

Usage (tests)::

    from app.main import create_app
    app = create_app()
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Application Factory ────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Build and return a fully-configured :class:`FastAPI` application.

    Steps:
    1. Load validated settings from environment / ``.env``.
    2. Register the async lifespan handler for startup/shutdown hooks.
    3. Attach CORS middleware.
    4. Mount the versioned API router.
    5. Register a top-level ``/health`` endpoint.
    """
    settings = get_settings()

    # ── Lifespan ────────────────────────────────────────────────────────

    @asynccontextmanager
    async def lifespan(application: FastAPI):  # noqa: ARG001 — required signature
        """Async context manager executed on startup and shutdown."""
        logger.info(
            "Application starting",
            extra={
                "app_name": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "debug": settings.DEBUG,
            },
        )
        # Start all active camera loops
        from app.cv.capture import camera_manager
        try:
            await camera_manager.start_all()
        except Exception as e:
            logger.error(f"Failed to start camera capture loops: {e}")
            
        yield
        
        logger.info("Application shutting down")
        # Stop all running camera loops
        try:
            await camera_manager.stop_all()
        except Exception as e:
            logger.error(f"Failed to stop camera capture loops: {e}")

    # ── FastAPI Instance ────────────────────────────────────────────────

    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "AI-Powered Smart Workspace Occupancy Monitoring Platform. "
            "Leverages computer vision and real-time analytics to track, "
            "visualize, and optimize workspace utilization."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── Middleware ──────────────────────────────────────────────────────

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ─────────────────────────────────────────────────────────

    from app.api.v1.router import router as v1_router  # noqa: E402 — deferred import
    from app.api.exceptions import register_exception_handlers  # noqa: E402

    register_exception_handlers(application)
    application.include_router(v1_router, prefix="/api/v1")

    # ── Health Check ────────────────────────────────────────────────────

    @application.get("/health", tags=["System"])
    async def health_check() -> dict:
        """Return basic health status of the application."""
        return {
            "status": "healthy",
            "version": settings.APP_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return application


# ── Module-Level Application Instance ───────────────────────────────────────
# Used by ``uvicorn app.main:app``

app: FastAPI = create_app()
