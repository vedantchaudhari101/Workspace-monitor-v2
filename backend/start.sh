#!/bin/sh
# Container entrypoint: optional demo seed, then the API (which also serves the web app).
set -e

if [ "${SEED_DEMO:-false}" = "true" ]; then
  # Idempotent: skips when the database already has a building.
  python -m scripts.seed_data || echo "Seeding skipped"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
