# Workspace Monitor

Seat-level workspace occupancy from ordinary camera video.

Upload footage of a room. The system calibrates the seat layout from the first frames, tracks which person owns which chair with YOLO pose estimation, and turns those observations into measured utilization, peak periods, team allocation figures and rule-based recommendations.

Built during an Advanced Analytics internship at Jio Platforms (report: *Chair Occupancy Detection*, Vedant Nitin Chaudhari, IIIT Guwahati).

---

## What it does

| Area | What you get |
|---|---|
| **Live** | Upload a video (or run the bundled sample). Watch real pipeline stages: upload → seat calibration → occupancy tracking → summary. The annotated stream shows seats in **red when occupied, green when available**, synced with a seat map drawn in the camera's own coordinates and a live activity feed. |
| **Session summary** | Per video: seats detected, peak occupancy and when, average occupancy, occupied seat-time, most/least used seat, peak period, per-seat sessions, plus calibration diagnostics and throughput. |
| **Analytics** | Time-weighted occupancy over 1 h – 7 days, hour-of-day profile, seat × hour heatmap, per-seat utilization (occupied, vacant, sessions, average and longest session), capacity, team utilization, CSV export. |
| **Explorer** | Every seat by floor and zone with filters (status, team, zone, utilization, label). Open any seat for its history and assign it to a team. |
| **Recommendations** | Measured insights, rule-based recommendations (each shows its rule and evidence), and the seat-allocation engine with approve/reject. |
| **Insights** | Workspace health score with published formulas, capacity warnings and unusual activity. |

### Honest data

* Every figure is computed from stored state changes and **measured in time**, never from event counts.
* Every occupancy event records where it came from (`VIDEO`, `MOCK`, `SEED`, `LEGACY`). Analytics use only real CV output unless you switch on **demo data**, and the UI labels demo data wherever it appears.
* When a video ends, every seat gets a closing `UNKNOWN` event, so a seat is never counted as occupied after the camera stopped watching it.
* Nothing is presented as machine learning that isn't. The forecast is labelled as a statistical model, and learned recommendations are listed as future work.

---

## Architecture

```
Browser (React 19 + Vite)
   │  REST  /api/v1/*              │  WebSocket /api/v1/occupancy/ws      │  MJPEG /camera/{id}/stream
   ▼                               ▼                                       ▼
FastAPI ──────────────────────────────────────────────────────────────────────────────
   │  services: seat_history (time-weighted analytics) · insights (rules) · recommendations
   │  cv/capture: one consumer per camera
   │     Phase 1  ChairDetector.calibrate()          yolov8n (chairs, couches, people, screens)
   │     Phase 2  SeatOccupancyProcessor             yolov8n-pose + ByteTrack, ~5 checks/s
   │     batched event writer → occupancy_events     session summary → analysis_sessions
   ▼
SQLite (default) or PostgreSQL 16 · Alembic migrations applied on startup
```

The production image serves the built web app from the API process, so one container and one URL run everything.

### Computer-vision pipeline (`backend/app/cv/processor.py`)

`CV_PIPELINE=report` (default) implements the method described in the project report:

* **Calibration** over the first `CALIBRATION_FRAMES` (150) frames: geometry gates on box size and shape; person-free frames preferred when at least 8 exist; confidence-ordered clustering with a merge radius of `min(w, h) × 0.5`; a persistence filter (≥ 15 % of frames); a static-object veto for screens and laptops misread as chairs; post-cluster NMS (centres within 6 % of the shorter side, plus nested-box duplicates).
* **Tracking**: torso-segment point weighted 70 % toward the hips; a velocity gate that ignores people moving more than 32 px (at 720p) between checks; exclusive ownership so one person can credit at most one seat, with a 30 % cross-axis expansion; the hip/knee posture check; and a 15/10 consecutive-reading hysteresis.
* **Seat identity**: re-uploading from the same camera matches new detections to known seats by IoU, so seat IDs, history and team assignments carry over. Seats that disappear are deactivated, never deleted.

`CV_PIPELINE=legacy` keeps the original IoU-clustering and containment pipeline for comparison.

---

## Run it locally

Requirements: Python 3.11+, Node 20+.

```bash
# Backend (API + CV) on :8000
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu   # CPU build, much smaller
pip install -r requirements.txt
cp .env.example .env
python -m scripts.seed_data          # optional: example building with demo data
uvicorn app.main:app --reload

# Frontend on :5173 (proxies /api to :8000)
cd frontend
npm install
npm run dev
```

Sign in with the bootstrap admin from `.env` (default `admin@workspace.dev` / `Admin@12345`). On first start the API applies migrations, creates the admin account, a building and a camera. YOLO weights download automatically the first time a video is processed.

### Docker

```bash
docker build -t workspace-monitor .
docker run -p 8000:8000 -e SEED_DEMO=true workspace-monitor      # SQLite, http://localhost:8000
docker compose up --build                                          # with PostgreSQL, http://localhost:8000
```

Hosting a public link for free on Oracle Cloud, step by step, is covered in [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Getting good results

* Use a fixed, elevated camera that can see the chairs, ideally the whole seat.
* Start the clip with the seats visible, and empty if you can. Calibration uses the first 150 frames; chairs hidden behind people at that point cannot be found.
* 720p–1080p at 15–30 fps is plenty. Processing runs at roughly real-time speed on a modern CPU.
* Ask everyone in the frame for permission before recording.

Known limitation (from the report): the system reasons in 2D, so a person standing still directly in front of a chair can look seated. The posture check reduces this but does not remove it.

---

## Configuration

All settings live in `backend/app/config.py` and can be set through environment variables. The most useful:

| Variable | Default | Purpose |
|---|---|---|
| `USE_SQLITE` / `SQLITE_PATH` | `true` / `workspace_monitor.db` | Database choice; set `USE_SQLITE=false` and `POSTGRES_*` for PostgreSQL |
| `CV_PIPELINE` | `report` | `report` or `legacy` |
| `YOLO_MODEL_PATH`, `POSE_MODEL_PATH` | `yolov8n.pt`, `yolov8n-pose.pt` | Weights for calibration and tracking |
| `OCC_FRAMES`, `CLEAR_FRAMES`, `VELOCITY_GATE_PX`, `HIP_WEIGHT`, `CROSS_EXPAND` | `15`, `10`, `32`, `0.7`, `0.3` | Tracking parameters from the report |
| `DEMO_MODE` | `false` | Simulate seeded cameras and include demo data by default |
| `SEED_DEMO` | `false` | (container) seed the example building on first start |
| `SHOW_DEMO_LOGIN` | `false` | Sign-in page offers the admin account; for public showcases only |
| `SAMPLE_VIDEO_PATH` | – | Video visitors can analyse with one click |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `SECRET_KEY` | – | Change these for any shared deployment |
| `FRONTEND_DIST` | – | Serve the built web app from the API |

---

## API

Interactive docs at `/docs`. Main endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/occupancy/camera/{id}/upload-video` | Upload a video and start an analysis session |
| `POST` | `/api/v1/occupancy/camera/{id}/sample` · `/stop` | Run the bundled sample · stop the current run |
| `GET` | `/api/v1/occupancy/camera/{id}/state` · `/stream` · `/snapshot` | Pipeline state · annotated MJPEG · reference still |
| `GET` | `/api/v1/occupancy/sessions` · `/sessions/{id}` | Analysis sessions and their summaries |
| `WS` | `/api/v1/occupancy/ws` | `state_sync`, `init_progress`, `seat_layout`, `processing_update`, `seat_transition`, `session_summary` |
| `GET` | `/api/v1/analytics/comprehensive/{building}` | Time-weighted KPIs, timeline, hourly, heatmap, seats, teams, capacity |
| `GET` | `/api/v1/analytics/seats/{seat}/history` | Seat intervals, stats and recorded state changes |
| `GET` | `/api/v1/analytics/activity/{building}` · `/insights/{building}` | Recent seat changes · health, insights and rule-based recommendations |
| `GET` | `/api/v1/workspace/context` · `/workspace/map/{building}` | Buildings, cameras, teams · floors, zones and seats for the explorer |
| `POST` | `/api/v1/recommendations/scan` · `/{id}/approve` · `/{id}/reject` | Seat-allocation engine |
| `POST` | `/api/v1/seats/allocations` | Assign a seat to a team |

---

## Project structure

```
backend/
  app/
    analytics/      intervals.py (time maths), session_summary.py, forecaster.py
    api/v1/         occupancy, analytics, workspace, recommendations, seats, startups, buildings, auth
    cv/             processor.py (calibration + tracking), capture.py (per-camera runtime)
    models/         SQLAlchemy models incl. analysis_session
    services/       seat_history.py, insights.py, recommendations.py, bootstrap.py
    db_migrate.py   applies Alembic migrations on startup
  alembic/versions/ 0001 baseline, 0002 sessions and event provenance
  scripts/seed_data.py
  tests/unit/
frontend/src/
  components/       shell (rail, ambient field, cursor), data (seat map, charts), ui, motion, feedback
  features/         analysis console + summary, seat drawer, activity feed
  lib/              live WebSocket store, workspace context, formatting
  pages/            Live, Analytics, Recommendations, Explorer, Insights, Session, Login
```

## Tests

```bash
cd backend && python -m pytest -q
```

## Credits

* [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) for detection and pose.
* Sample footage used in development: `classroom.mp4` from [intel-iot-devkit/sample-videos](https://github.com/intel-iot-devkit/sample-videos), CC BY 4.0.

## License

MIT
