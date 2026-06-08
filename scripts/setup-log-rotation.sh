#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="${1:-/var/log/running-club}"
mkdir -p "$LOG_DIR"

cat > "$LOG_DIR/logrotate.conf" <<'EOF'
/var/log/running-club/*.log {
  daily
  rotate 7
  missingok
  compress
  delaycompress
  notifempty
  copytruncate
}
EOF

echo "Wrote log rotation config to $LOG_DIR/logrotate.conf"
