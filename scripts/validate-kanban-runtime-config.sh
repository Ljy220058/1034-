#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${ROOT_DIR}/deploy/kanban-task-runtime.example.yml"
DOC_FILE="${ROOT_DIR}/docs/kanban-runtime-retry.md"

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

require_file() {
  local file="$1"
  [[ -f "$file" ]] || fail "缺少文件：$file"
}

require_pattern() {
  local file="$1"
  local pattern="$2"
  local message="$3"
  grep -Eq "$pattern" "$file" || fail "$message"
}

require_file "$CONFIG_FILE"
require_file "$DOC_FILE"

require_pattern "$CONFIG_FILE" 'max_runtime_seconds:[[:space:]]*3600' '配置示例必须提供默认 max_runtime_seconds: 3600'
require_pattern "$CONFIG_FILE" 'max_retries:[[:space:]]*2' '配置示例必须提供默认 max_retries: 2'
require_pattern "$CONFIG_FILE" 'requeue_strategy:[[:space:]]*retry_transient' '配置示例必须提供默认 requeue_strategy: retry_transient'
require_pattern "$CONFIG_FILE" 'timeout:' '配置示例必须覆盖 timeout 状态'
require_pattern "$CONFIG_FILE" 'transient_failure:' '配置示例必须覆盖 transient_failure 状态'
require_pattern "$CONFIG_FILE" 'permanent_failure:' '配置示例必须覆盖 permanent_failure 状态'
require_pattern "$CONFIG_FILE" 'retries_exhausted:' '配置示例必须覆盖 retries_exhausted 状态'
require_pattern "$CONFIG_FILE" 'message_zh:' '配置示例必须包含中文提示字段 message_zh'
require_pattern "$CONFIG_FILE" '已达到最大重试次数|重新入队|人工判断' '配置示例必须包含面向调度器的中文错误提示'
require_pattern "$CONFIG_FILE" 'never_retry_destructive' '配置示例必须说明破坏性任务不自动重试'
require_pattern "$CONFIG_FILE" 'block_when:' '配置示例必须说明何时阻断'
require_pattern "$CONFIG_FILE" 'retry_when:' '配置示例必须说明何时重试'

require_pattern "$DOC_FILE" 'max_runtime_seconds' '中文说明必须解释 max_runtime_seconds'
require_pattern "$DOC_FILE" 'max_retries' '中文说明必须解释 max_retries'
require_pattern "$DOC_FILE" '重新入队|ready' '中文说明必须解释失败后重新入队策略'
require_pattern "$DOC_FILE" '阻断|blocked|人工' '中文说明必须解释何时阻断'
require_pattern "$DOC_FILE" 'validate-kanban-runtime-config.sh' '中文说明必须包含本地验证脚本路径'

if command -v python >/dev/null 2>&1; then
  python - "$CONFIG_FILE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding='utf-8')
required_order = ['kanban_task_policy:', 'defaults:', 'status_mapping:', 'decision_rules:', 'per_task_overrides:']
positions = [text.find(item) for item in required_order]
missing = [item for item, pos in zip(required_order, positions) if pos < 0]
if missing:
    raise SystemExit(f"ERROR: 缺少配置段：{', '.join(missing)}")
if positions != sorted(positions):
    raise SystemExit('ERROR: 配置段顺序应为 defaults → status_mapping → decision_rules → per_task_overrides')
print('OK: structure order verified')
PY
fi

printf 'OK: kanban task runtime/retry config example is valid\n'
