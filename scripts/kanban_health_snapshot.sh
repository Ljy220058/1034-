#!/usr/bin/env bash
set -euo pipefail

# 跑团任务运行健康快照脚本。
# 只读读取 Hermes Kanban SQLite 数据库，或读取 --sample-json 示例数据；不修改任务状态。
# 用法：scripts/kanban_health_snapshot.sh [--db /path/to/kanban.db] [--sample-json docs/kanban_health_snapshot_samples.json] [--scenario normal|long_running|blocked]

KANBAN_DB="${HERMES_KANBAN_DB:-${HOME:-/root}/.hermes/kanban.db}"
SAMPLE_JSON=""
SCENARIO=""
LONG_RUNNING_HOURS="${KANBAN_SNAPSHOT_LONG_RUNNING_HOURS:-2}"
TODO_AGE_HOURS="${KANBAN_SNAPSHOT_TODO_AGE_HOURS:-24}"
LIMIT="${KANBAN_SNAPSHOT_LIMIT:-200}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db)
      KANBAN_DB="${2:?--db 需要路径}"
      shift 2
      ;;
    --sample-json)
      SAMPLE_JSON="${2:?--sample-json 需要路径}"
      shift 2
      ;;
    --scenario)
      SCENARIO="${2:?--scenario 需要 normal|long_running|blocked}"
      shift 2
      ;;
    --long-running-hours)
      LONG_RUNNING_HOURS="${2:?--long-running-hours 需要数字}"
      shift 2
      ;;
    --todo-age-hours)
      TODO_AGE_HOURS="${2:?--todo-age-hours 需要数字}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:?--limit 需要数字}"
      shift 2
      ;;
    -h|--help)
      sed -n '1,40p' "$0"
      exit 0
      ;;
    *)
      echo "未知参数：$1" >&2
      exit 2
      ;;
  esac
done

export KANBAN_DB SAMPLE_JSON SCENARIO LONG_RUNNING_HOURS TODO_AGE_HOURS LIMIT

run_python() {
  if command -v python3 >/dev/null 2>&1; then
    python3 "$@"
  elif command -v python >/dev/null 2>&1; then
    python "$@"
  elif command -v uv >/dev/null 2>&1; then
    uv run python "$@"
  else
    echo "未找到 python3/python/uv，无法生成快照。" >&2
    exit 127
  fi
}

run_python - <<'PY'
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

KANBAN_DB = os.environ.get("KANBAN_DB", "")
SAMPLE_JSON = os.environ.get("SAMPLE_JSON", "")
SCENARIO = os.environ.get("SCENARIO", "")
LONG_RUNNING_HOURS = float(os.environ.get("LONG_RUNNING_HOURS", "2"))
TODO_AGE_HOURS = float(os.environ.get("TODO_AGE_HOURS", "24"))
LIMIT = int(os.environ.get("LIMIT", "200"))
NOW = int(time.time())

WATCH_STATUSES = {"running", "ready", "todo", "blocked", "triage"}


def fmt_ts(value: Any) -> str:
    if value in (None, "", 0):
        return "-"
    try:
        return datetime.fromtimestamp(int(value)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


def hours_since(value: Any) -> float | None:
    if value in (None, "", 0):
        return None
    try:
        return max(0.0, (NOW - int(value)) / 3600.0)
    except Exception:
        return None


def age_text(value: Any) -> str:
    h = hours_since(value)
    if h is None:
        return "-"
    if h < 1:
        return f"{h * 60:.0f} 分钟"
    if h < 48:
        return f"{h:.1f} 小时"
    return f"{h / 24:.1f} 天"


def yes_no(value: bool) -> str:
    return "是" if value else "否"


def one_line(text: Any, max_len: int = 120) -> str:
    if text in (None, ""):
        return "-"
    text = str(text).replace("\r", " ").replace("\n", " ").strip()
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def load_from_sample(path: str, scenario: str) -> list[dict[str, Any]]:
    sample_path = Path(path).expanduser()
    with sample_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict) and "scenarios" in raw:
        scenarios = raw["scenarios"]
        scenario = scenario or "normal"
        if scenario not in scenarios:
            print(f"示例场景不存在：{scenario}；可选：{', '.join(sorted(scenarios))}", file=sys.stderr)
            sys.exit(2)
        tasks = scenarios[scenario]
    elif isinstance(raw, list):
        tasks = raw
    else:
        print("示例 JSON 格式错误：应为任务数组，或包含 scenarios 对象。", file=sys.stderr)
        sys.exit(2)
    # 支持相对 now 的秒数，便于样例长期稳定。
    normalized: list[dict[str, Any]] = []
    for item in tasks:
        row = dict(item)
        for key in ("created_at", "started_at", "last_heartbeat_at"):
            rel_key = f"{key}_age_seconds"
            if rel_key in row and row.get(key) in (None, "", 0):
                row[key] = NOW - int(row[rel_key])
        normalized.append(row)
    return normalized


def load_from_db(path: str) -> list[dict[str, Any]]:
    db_path = Path(path).expanduser()
    if not db_path.exists():
        print(f"看板数据库不存在：{db_path}", file=sys.stderr)
        print("可改用示例验证：scripts/kanban_health_snapshot.sh --sample-json docs/kanban_health_snapshot_samples.json --scenario normal", file=sys.stderr)
        sys.exit(2)
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT id, title, assignee, status, created_at, started_at, workspace_kind, workspace_path,
               current_run_id, max_runtime_seconds, last_heartbeat_at, consecutive_failures, last_failure_error
        FROM tasks
        WHERE status IN ('running', 'ready', 'todo', 'blocked', 'triage')
        ORDER BY
          CASE status WHEN 'running' THEN 1 WHEN 'blocked' THEN 2 WHEN 'ready' THEN 3 WHEN 'todo' THEN 4 ELSE 5 END,
          COALESCE(started_at, created_at) ASC
        LIMIT ?
        """,
        (LIMIT,),
    ).fetchall()
    return [dict(row) for row in rows]


def possible_timeout(task: dict[str, Any]) -> tuple[bool, str]:
    status = str(task.get("status") or "")
    started_at = task.get("started_at")
    max_runtime = task.get("max_runtime_seconds")
    if status == "running":
        run_hours = hours_since(started_at)
        heartbeat_hours = hours_since(task.get("last_heartbeat_at"))
        if max_runtime:
            try:
                max_hours = float(max_runtime) / 3600.0
                if run_hours is not None and run_hours >= max_hours:
                    return True, f"已运行 {run_hours:.1f}h，超过 max_runtime {max_hours:.1f}h"
            except Exception:
                pass
        if run_hours is not None and run_hours >= LONG_RUNNING_HOURS:
            if heartbeat_hours is not None and heartbeat_hours < 1:
                return True, f"已运行 {run_hours:.1f}h；有近 1h 心跳但需关注"
            return True, f"已运行 {run_hours:.1f}h，超过阈值 {LONG_RUNNING_HOURS:.1f}h"
    if status in {"todo", "ready", "triage"}:
        wait_hours = hours_since(task.get("created_at"))
        if wait_hours is not None and wait_hours >= TODO_AGE_HOURS:
            return True, f"等待 {wait_hours:.1f}h，超过待办阈值 {TODO_AGE_HOURS:.1f}h"
    return False, "-"


def status_label(status: str) -> str:
    labels = {"running": "运行中", "ready": "可领取", "todo": "待办", "blocked": "阻塞", "triage": "待细化"}
    return labels.get(status, status or "未知")


def build_snapshot(tasks: list[dict[str, Any]], source: str) -> str:
    status_counts = Counter(str(t.get("status") or "unknown") for t in tasks)
    by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    long_items: list[tuple[dict[str, Any], str]] = []
    blocked_items: list[dict[str, Any]] = []
    timeout_flags: dict[str, tuple[bool, str]] = {}

    for task in tasks:
        assignee = str(task.get("assignee") or "未分配")
        by_worker[assignee].append(task)
        flag, reason = possible_timeout(task)
        timeout_flags[str(task.get("id"))] = (flag, reason)
        if flag:
            long_items.append((task, reason))
        if str(task.get("status") or "") == "blocked":
            blocked_items.append(task)

    lines: list[str] = []
    lines.append("跑团项目 Kanban 任务运行健康快照")
    lines.append("==============================")
    lines.append(f"生成时间：{fmt_ts(NOW)}")
    lines.append(f"数据来源：{source}")
    lines.append(f"超时判断：running >= {LONG_RUNNING_HOURS:g}h；todo/ready/triage >= {TODO_AGE_HOURS:g}h；如任务设置 max_runtime_seconds 则优先使用该值")
    lines.append("")

    lines.append("一、总体计数")
    lines.append(f"- 关注任务总数：{len(tasks)}")
    for key in ("running", "blocked", "ready", "todo", "triage"):
        lines.append(f"- {status_label(key)}：{status_counts.get(key, 0)}")
    unknown = sum(v for k, v in status_counts.items() if k not in WATCH_STATUSES)
    if unknown:
        lines.append(f"- 其他状态：{unknown}")
    lines.append(f"- 可能超时/长时间未完成：{len(long_items)}")
    lines.append("")

    lines.append("二、按 worker 分组")
    if not by_worker:
        lines.append("- 当前没有 running/todo/blocked/ready/triage 任务。")
    for assignee in sorted(by_worker):
        group = by_worker[assignee]
        counts = Counter(str(t.get("status") or "unknown") for t in group)
        parts = [f"{status_label(k)} {counts[k]}" for k in sorted(counts)]
        lines.append(f"- {assignee}：{len(group)} 个（{', '.join(parts)}）")
        for task in group[:8]:
            flag, reason = timeout_flags.get(str(task.get("id")), (False, "-"))
            lines.append(
                f"  - {task.get('id', '-')}｜{status_label(str(task.get('status') or ''))}｜创建 {fmt_ts(task.get('created_at'))}｜"
                f"启动 {fmt_ts(task.get('started_at'))}｜工作区 {task.get('workspace_path') or '-'}｜可能超时：{yes_no(flag)}（{reason}）｜{one_line(task.get('title'))}"
            )
        if len(group) > 8:
            lines.append(f"  - ……另有 {len(group) - 8} 个任务未展开，可调大 KANBAN_SNAPSHOT_LIMIT 或查看数据库。")
    lines.append("")

    lines.append("三、长时间 running / 长时间未完成提醒")
    if not long_items:
        lines.append("- 未发现超过阈值的 running 或等待过久任务。")
    else:
        for task, reason in long_items[:20]:
            lines.append(
                f"- {task.get('id', '-')}｜worker={task.get('assignee') or '未分配'}｜状态={status_label(str(task.get('status') or ''))}｜"
                f"运行/等待={age_text(task.get('started_at') or task.get('created_at'))}｜当前 run={task.get('current_run_id') or '-'}｜原因：{reason}"
            )
    lines.append("")

    lines.append("四、建议下一步动作")
    if blocked_items:
        lines.append(f"- 先处理 {len(blocked_items)} 个 blocked：阅读评论线程，补齐人工决策后再 unblock。")
        for task in blocked_items[:5]:
            lines.append(f"  - {task.get('id', '-')}｜worker={task.get('assignee') or '未分配'}｜{one_line(task.get('title'))}")
    if long_items:
        lines.append("- 对长时间 running：检查 current_run_id 对应日志、last_heartbeat_at 和进程存活；无心跳超过 1h 的任务可等待 dispatcher 回收或人工复核。")
    if status_counts.get("ready", 0) or status_counts.get("todo", 0):
        lines.append("- 对 ready/todo 堆积：按 assignee 查看是否 worker 离线、并发不足或父任务未完成。")
    if not blocked_items and not long_items and not status_counts.get("ready", 0) and not status_counts.get("todo", 0):
        lines.append("- 当前无明显异常；保持调度器运行，下一轮快照继续观察即可。")
    lines.append("- 本报告可直接复制到 kanban 评论；脚本只读，不会修改线上调度配置。")
    return "\n".join(lines)


def main() -> None:
    if SAMPLE_JSON:
        tasks = load_from_sample(SAMPLE_JSON, SCENARIO)
        source = f"示例 JSON：{SAMPLE_JSON}（scenario={SCENARIO or 'normal'}）"
    else:
        tasks = load_from_db(KANBAN_DB)
        source = f"SQLite 只读：{KANBAN_DB}"
    print(build_snapshot(tasks, source))


if __name__ == "__main__":
    main()
PY
