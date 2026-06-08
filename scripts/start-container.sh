#!/usr/bin/env bash
set -euo pipefail

APP_NAME="1034-running-club"
CONTAINER_NAME="${APP_NAME}-container"
IMAGE_TAG="${APP_NAME}:1.0.0"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${RUNNING_CLUB_DATA_DIR:-/var/lib/1034-running-club}"
LOG_DIR="${RUNNING_CLUB_LOG_DIR:-/var/log/1034-running-club}"
PORT="${RUNNING_CLUB_PORT:-8000}"

mkdir -p "${DATA_DIR}" "${LOG_DIR}"

if command -v docker >/dev/null 2>&1; then
  docker build -t "${IMAGE_TAG}" "${PROJECT_DIR}"
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  docker run -d \
    --name "${CONTAINER_NAME}" \
    --restart unless-stopped \
    -p "${PORT}:8000" \
    -e RUNNING_CLUB_DB_PATH=/data/running_club.db \
    -e RUNNING_CLUB_HOST=0.0.0.0 \
    -e RUNNING_CLUB_PORT=8000 \
    -v "${DATA_DIR}:/data" \
    "${IMAGE_TAG}"
  exit 0
fi

if command -v docker-compose >/dev/null 2>&1; then
  (cd "${PROJECT_DIR}" && docker-compose up -d --build)
  exit 0
fi

if command -v podman >/dev/null 2>&1; then
  podman build -t "${IMAGE_TAG}" "${PROJECT_DIR}"
  podman rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  podman run -d \
    --name "${CONTAINER_NAME}" \
    --restart unless-stopped \
    -p "${PORT}:8000" \
    -e RUNNING_CLUB_DB_PATH=/data/running_club.db \
    -e RUNNING_CLUB_HOST=0.0.0.0 \
    -e RUNNING_CLUB_PORT=8000 \
    -v "${DATA_DIR}:/data" \
    "${IMAGE_TAG}"
  exit 0
fi

echo "docker or podman is required" >&2
exit 1
