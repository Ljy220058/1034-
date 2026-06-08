#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

python - <<'PY'
from datetime import datetime, timedelta, timezone

from backend.kanban_helper import DEFAULT_CREATION_SOURCE, DEFAULT_WORKSPACE, create_task_payloads, dedupe_task_payloads

now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)
payloads = create_task_payloads()
assert len(payloads) == 2, '必须生成两个基准创意任务'

same_title_existing = [{
    'title': payloads[0]['title'],
    'assignee': 'other-worker',
    'workspace_path': DEFAULT_WORKSPACE,
    'created_by': DEFAULT_CREATION_SOURCE,
    'updated_at': (now - timedelta(minutes=5)).isoformat(),
}]
assert dedupe_task_payloads([payloads[0]], same_title_existing, now=now) == [], '重复标题应被过滤'

same_assignee_existing = [{
    'title': '另一个创意任务标题',
    'assignee': payloads[0]['assignee'],
    'workspace_path': DEFAULT_WORKSPACE,
    'created_by': DEFAULT_CREATION_SOURCE,
    'updated_at': (now - timedelta(minutes=5)).isoformat(),
}]
assert dedupe_task_payloads([payloads[0]], same_assignee_existing, now=now) == [], '同一负责人短时间重复分配应被过滤'

different_workspace_existing = [{
    'title': payloads[0]['title'],
    'assignee': payloads[0]['assignee'],
    'workspace_path': '/tmp/another-workspace',
    'created_by': DEFAULT_CREATION_SOURCE,
    'updated_at': (now - timedelta(minutes=5)).isoformat(),
}]
assert dedupe_task_payloads([payloads[0]], different_workspace_existing, now=now) == [payloads[0]], '不同工作区不应误判重复'

print('OK: 创意任务去重验证通过（重复标题、同负责人、不同工作区三种情况均覆盖）')
PY
