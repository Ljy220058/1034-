#!/usr/bin/env sh
set -eu

: "${HEALTHCHECK_URL:=http://web:8000/health}"
: "${CRON_HEALTH_INTERVAL_SECONDS:=300}"
: "${HERMES_KANBAN_TASK:=}"
: "${HERMES_KANBAN_BOARD:=default}"

while true; do
  status=0
  if wget -q -T 10 -O - "$HEALTHCHECK_URL" >/tmp/cron-health.out 2>/tmp/cron-health.err; then
    body=$(tr -d '\n' </tmp/cron-health.out)
    msg="cron health ok: ${HEALTHCHECK_URL} -> ${body:-no-body}"
  else
    status=$?
    err=$(tr -d '\n' </tmp/cron-health.err)
    msg="cron health failed: ${HEALTHCHECK_URL} (exit ${status}): ${err:-no-error}"
  fi

  if [ -n "$HERMES_KANBAN_TASK" ]; then
    python - <<'PY' "$HERMES_KANBAN_BOARD" "$HERMES_KANBAN_TASK" "$msg"
import sys
board, task_id, msg = sys.argv[1:4]
try:
    from hermes_tools import kanban_comment
    kanban_comment(board=board, task_id=task_id, body=msg)
except Exception:
    pass
PY
  else
    printf '%s\n' "$msg"
  fi

  sleep "$CRON_HEALTH_INTERVAL_SECONDS"
done
