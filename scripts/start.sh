#!/usr/bin/env sh
set -eu

: "${RUNNING_CLUB_DB_PATH:=/data/running_club.db}"
: "${UVICORN_HOST:=0.0.0.0}"
: "${UVICORN_PORT:=8000}"
: "${UVICORN_WORKERS:=1}"

mkdir -p "$(dirname "$RUNNING_CLUB_DB_PATH")"
python - <<'PY'
from backend.db import initialize_database
initialize_database()
PY

exec uvicorn backend.main:app --host "$UVICORN_HOST" --port "$UVICORN_PORT" --workers "$UVICORN_WORKERS"
