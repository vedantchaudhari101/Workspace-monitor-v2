# =============================================================================
# Workspace Monitor — single-container image (API + CV pipeline + web app)
#
# Builds the React app, installs the FastAPI backend with CPU-only PyTorch,
# bakes in the YOLO weights and serves everything from one port.
# Works as-is on Hugging Face Spaces (Docker SDK), Render, Railway or Fly.io.
#
#   docker build -t workspace-monitor .
#   docker run -p 7860:7860 workspace-monitor
# =============================================================================

# ── Stage 1: web app ─────────────────────────────────────────────────────────
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── Stage 2: API + CV runtime ───────────────────────────────────────────────
FROM python:3.12-slim

ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG YOLO_RELEASE=https://github.com/ultralytics/assets/releases/download/v8.3.0
# Optional one-click sample for visitors. Replace with your own footage URL,
# or pass --build-arg SAMPLE_VIDEO_URL= to ship without one.
ARG SAMPLE_VIDEO_URL=https://github.com/intel-iot-devkit/sample-videos/raw/master/classroom.mp4
ARG SAMPLE_VIDEO_CREDIT="classroom.mp4 from Intel IoT DevKit sample videos, CC BY 4.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    YOLO_CONFIG_DIR=/tmp/Ultralytics

RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces run containers as uid 1000.
RUN useradd -m -u 1000 app
WORKDIR /app

# CPU-only PyTorch first, so ultralytics doesn't pull the multi-GB CUDA build.
RUN pip install torch torchvision --index-url ${TORCH_INDEX_URL}
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/ ./
COPY --from=web /web/dist ./frontend_dist

RUN mkdir -p models samples /data \
    && curl -fsSL -o models/yolov8n.pt ${YOLO_RELEASE}/yolov8n.pt \
    && curl -fsSL -o models/yolov8n-pose.pt ${YOLO_RELEASE}/yolov8n-pose.pt \
    && if [ -n "${SAMPLE_VIDEO_URL}" ]; then curl -fsSL -o samples/sample.mp4 "${SAMPLE_VIDEO_URL}" || true; fi \
    && chmod +x start.sh \
    && chown -R app:app /app /data

USER app

ENV PORT=7860 \
    FRONTEND_DIST=/app/frontend_dist \
    SQLITE_PATH=/data/workspace_monitor.db \
    UPLOAD_DIR=/data/uploads \
    YOLO_MODEL_PATH=/app/models/yolov8n.pt \
    POSE_MODEL_PATH=/app/models/yolov8n-pose.pt \
    SAMPLE_VIDEO_PATH=/app/samples/sample.mp4 \
    SAMPLE_VIDEO_CREDIT="${SAMPLE_VIDEO_CREDIT}" \
    MAX_UPLOAD_MB=200

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fs http://localhost:${PORT}/health || exit 1

CMD ["./start.sh"]
