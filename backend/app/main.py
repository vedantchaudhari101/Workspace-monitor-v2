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
        # Schema first, then the minimum workspace structure, then cameras.
        if settings.RUN_MIGRATIONS:
            import asyncio

            from app.db_migrate import run_migrations

            await asyncio.get_running_loop().run_in_executor(None, run_migrations)
        try:
            from app.database import async_session_factory
            from app.services.bootstrap import bootstrap

            async with async_session_factory() as session:
                await bootstrap(session)
        except Exception as e:
            logger.error(f"Bootstrap failed: {e}")

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

    @application.get("/api/v1/config", tags=["System"])
    async def public_config() -> dict:
        """Non-secret runtime flags the frontend needs before login."""
        return {
            "demo_mode": settings.DEMO_MODE,
            "pipeline": settings.CV_PIPELINE,
            "max_upload_mb": settings.MAX_UPLOAD_MB,
            "version": settings.APP_VERSION,
        }

    _mount_frontend(application, settings.FRONTEND_DIST)
    return application


def _mount_frontend(application: FastAPI, dist: str) -> None:
    """Serve a built SPA from the API process (single-container deployments)."""
    import os

    if not dist or not os.path.isdir(dist):
        return
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    assets = os.path.join(dist, "assets")
    if os.path.isdir(assets):
        application.mount("/assets", StaticFiles(directory=assets), name="assets")
    index = os.path.join(dist, "index.html")

    @application.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        from fastapi import HTTPException

        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        root = os.path.abspath(dist)
        candidate = os.path.abspath(os.path.join(root, full_path))
        if full_path and candidate.startswith(root + os.sep) and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(index)

    logger.info(f"Serving frontend from {dist}")


# ── Module-Level Application Instance ───────────────────────────────────────
# Used by ``uvicorn app.main:app``

app: FastAPI = create_app()
