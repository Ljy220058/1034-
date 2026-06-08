#!/usr/bin/env bash
set -euo pipefail

# 只读任务日志巡检脚本：不修改任务状态、不杀进程、不启动长驻服务。
# 用法：scripts/readonly_task_log_inspector.sh [任务编号]

TASK_ID="${1:-${HERMES_KANBAN_TASK:-}}"
KANBAN_DB="${HERMES_KANBAN_DB:-${HOME:-/root}/.hermes/kanban.db}"
WORKSPACE="${HERMES_KANBAN_WORKSPACE:-$(pwd)}"
EVENT_LIMIT="${KANBAN_INSPECT_EVENT_LIMIT:-12}"
RUN_LIMIT="${KANBAN_INSPECT_RUN_LIMIT:-8}"
LOG_LIMIT="${KANBAN_INSPECT_LOG_LIMIT:-5}"

export TASK_ID KANBAN_DB WORKSPACE EVENT_LIMIT RUN_LIMIT LOG_LIMIT

python - <<'PY'
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

TASK_ID = os.environ.get("TASK_ID", "").strip()
KANBAN_DB = os.environ.get("KANBAN_DB", "").strip()
WORKSPACE = Path(os.environ.get("WORKSPACE", ".")).resolve()
EVENT_LIMIT = int(os.environ.get("EVENT_LIMIT", "12"))
RUN_LIMIT = int(os.environ.get("RUN_LIMIT", "8"))
LOG_LIMIT = int(os.environ.get("LOG_LIMIT", "5"))


def ts(value: Any) -> str:
    if value in (None, ""):
        return "-"
    try:
        return datetime.fromtimestamp(int(value)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


def safe_json(text: Any) -> Any:
    if text in (None, ""):
        return None
    if isinstance(text, (dict, list)):
        return text
    try:
        return json.loads(text)
    except Exception:
        return text


def one_line(text: Any, max_len: int = 260) -> str:
    if text is None:
        return "-"
    if isinstance(text, (dict, list)):
        text = json.dumps(text, ensure_ascii=False, sort_keys=True)
    text = str(text).replace("\r", " ").replace("\n", " ").strip()
    if not text:
        return "-"
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def print_hint(title: str, lines: list[str]) -> None:
    print(f"\n【{title}】")
    for line in lines:
        print(f"- {line}")


def connect_ro(db_path: str) -> sqlite3.Connection | None:
    if not db_path:
        print_hint("无法读取看板数据库", [
            "未设置 HERMES_KANBAN_DB，也无法推导默认路径。",
            "可执行：export HERMES_KANBAN_DB=/root/.hermes/kanban.db 后重试。",
        ])
        return None
    path = Path(db_path).expanduser()
    if not path.exists():
        print_hint("无法读取看板数据库", [
            f"数据库不存在：{path}",
            "请在 Hermes Kanban 工作节点环境中运行，或显式传入：HERMES_KANBAN_DB=/path/to/kanban.db scripts/readonly_task_log_inspector.sh <任务编号>",
        ])
        return None
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        return con
    except Exception as exc:
        print_hint("无法以只读模式打开看板数据库", [
            f"路径：{path}",
            f"错误：{exc}",
            "请检查文件权限，示例：ls -l \"$HERMES_KANBAN_DB\"。",
        ])
        return None


def discover_workspace_logs(workspace: Path, limit: int) -> list[Path]:
    if not workspace.exists():
        return []
    names: list[Path] = []
    preferred_dirs = [workspace / "logs", workspace / ".logs", workspace / "tmp", workspace / "var" / "log"]
    candidates: list[Path] = []
    for base in preferred_dirs:
        if base.exists() and base.is_dir():
            candidates.extend(base.rglob("*.log"))
            candidates.extend(base.rglob("*.out"))
            candidates.extend(base.rglob("*.err"))
    if not candidates:
        for pattern in ("*.log", "*.out", "*.err"):
            candidates.extend(workspace.glob(pattern))
    seen: set[Path] = set()
    for item in candidates:
        try:
            p = item.resolve()
            if p in seen or not p.is_file():
                continue
            seen.add(p)
            names.append(p)
        except Exception:
            continue
    names.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return names[:limit]


def suggest_next_step(task: sqlite3.Row | None, runs: list[sqlite3.Row], events: list[sqlite3.Row]) -> str:
    latest_error = ""
    for run in runs:
        if run["error"]:
            latest_error = str(run["error"])
            break
    if not latest_error and task and task["last_failure_error"]:
        latest_error = str(task["last_failure_error"])
    if "without calling kanban_complete or kanban_block" in latest_error:
        return "上一轮干净退出但未写回完成/阻塞状态；下一步检查 worker 末尾是否遗漏 kanban_complete，或是否被包装脚本提前 exit 0。"
    if "not alive" in latest_error or "crashed" in latest_error:
        return "worker 进程异常退出；下一步查看对应 run_id 的 stderr/会话日志，并本地复现 worker 启动命令。"
    if task and task["status"] == "running":
        return "任务仍处于运行中；下一步确认 current_run_id 对应进程是否仍在产生日志，必要时等待 dispatcher 回收。"
    if task and task["status"] == "blocked":
        return "任务已阻塞；下一步阅读评论线程中的人工答复或阻塞原因后再继续。"
    if task and task["status"] == "done":
        return "任务已完成；下一步只需抽查最近事件和完成摘要是否符合预期。"
    return "未发现明确失败摘要；下一步扩大事件数量：KANBAN_INSPECT_EVENT_LIMIT=50 scripts/readonly_task_log_inspector.sh <任务编号>。"


print("只读任务日志巡检报告")
print("====================")
print(f"巡检时间：{ts(datetime.now().timestamp())}")
print(f"工作区：{WORKSPACE}")
print(f"看板数据库：{KANBAN_DB or '-'}")

if not TASK_ID:
    print_hint("缺少任务编号", [
        "请传入任务编号，例如：scripts/readonly_task_log_inspector.sh t_0f23ae55。",
        "也可以先设置环境变量：export HERMES_KANBAN_TASK=t_0f23ae55。",
    ])
    sys.exit(2)

con = connect_ro(KANBAN_DB)
if con is None:
    sys.exit(2)

try:
    task = con.execute("SELECT * FROM tasks WHERE id = ?", (TASK_ID,)).fetchone()
except sqlite3.Error as exc:
    print_hint("看板表结构不匹配", [
        f"查询 tasks 表失败：{exc}",
        "请确认这是 Hermes Kanban 数据库，而不是业务数据库。",
    ])
    sys.exit(2)

if task is None:
    print_hint("未找到任务", [
        f"任务编号不存在：{TASK_ID}",
        "可执行：hermes kanban list --all 查找任务编号；本脚本不会修改任何状态。",
    ])
    sys.exit(1)

runs = con.execute(
    "SELECT * FROM task_runs WHERE task_id = ? ORDER BY started_at DESC, id DESC LIMIT ?",
    (TASK_ID, RUN_LIMIT),
).fetchall()
events = con.execute(
    "SELECT * FROM task_events WHERE task_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
    (TASK_ID, EVENT_LIMIT),
).fetchall()
comments = con.execute(
    "SELECT * FROM task_comments WHERE task_id = ? ORDER BY created_at DESC, id DESC LIMIT 5",
    (TASK_ID,),
).fetchall()

print("\n【任务概览】")
print(f"任务编号：{task['id']}")
print(f"标题：{task['title']}")
print(f"负责人：{task['assignee'] or '-'}")
print(f"状态：{task['status']}")
print(f"优先级：{task['priority']}")
print(f"创建者：{task['created_by'] or '-'}")
print(f"创建时间：{ts(task['created_at'])}")
print(f"开始时间：{ts(task['started_at'])}")
print(f"完成时间：{ts(task['completed_at'])}")
print(f"工作区类型：{task['workspace_kind']}")
print(f"工作区路径：{task['workspace_path'] or '-'}")
print(f"当前运行编号：{task['current_run_id'] or '-'}")
print(f"连续失败次数：{task['consecutive_failures']}")
print(f"最近失败摘要：{one_line(task['last_failure_error'])}")

print("\n【最近运行失败摘要】")
if not runs:
    print("- 未找到运行记录。可确认 dispatcher 是否已领取该任务，或扩大数据库检查范围。")
else:
    for run in runs:
        meta = safe_json(run["metadata"])
        payload = one_line(meta, 220)
        print(
            f"- run_id={run['id']}，状态={run['status']}，结果={run['outcome'] or '-'}，"
            f"开始={ts(run['started_at'])}，结束={ts(run['ended_at'])}，"
            f"错误={one_line(run['error'])}，元数据={payload}"
        )

print("\n【最近事件】")
if not events:
    print("- 未找到事件记录。可执行：KANBAN_INSPECT_EVENT_LIMIT=50 scripts/readonly_task_log_inspector.sh " + TASK_ID)
else:
    for ev in events:
        print(f"- {ts(ev['created_at'])}，事件={ev['kind']}，run_id={ev['run_id'] or '-'}，详情={one_line(safe_json(ev['payload']), 260)}")

print("\n【最近错误片段】")
error_lines: list[str] = []
for run in runs:
    if run["error"]:
        error_lines.append(f"run_id={run['id']}：{one_line(run['error'], 360)}")
for ev in events:
    payload = safe_json(ev["payload"])
    text = one_line(payload, 360)
    if ev["kind"] in {"crashed", "gave_up", "protocol_violation", "timed_out", "spawn_failed"} or "error" in text.lower():
        error_lines.append(f"事件 {ev['kind']}：{text}")
if task["last_failure_error"]:
    error_lines.append(f"任务 last_failure_error：{one_line(task['last_failure_error'], 360)}")
if not error_lines:
    print("- 未发现明确错误片段。")
else:
    for line in error_lines[:8]:
        print(f"- {line}")

print("\n【最近评论】")
if not comments:
    print("- 暂无评论。")
else:
    for c in comments:
        print(f"- {ts(c['created_at'])}，{c['author']}：{one_line(c['body'], 260)}")

print("\n【工作区日志线索】")
logs = discover_workspace_logs(WORKSPACE, LOG_LIMIT)
if logs:
    for p in logs:
        try:
            stat = p.stat()
            print(f"- {p}，大小={stat.st_size} 字节，修改时间={ts(stat.st_mtime)}")
            try:
                tail = p.read_text(errors="replace").splitlines()[-3:]
                for line in tail:
                    print(f"  片段：{one_line(line, 220)}")
            except Exception as exc:
                print(f"  提示：无法读取片段：{exc}")
        except Exception:
            print(f"- {p}")
else:
    print("- 当前工作区未发现 *.log、*.out、*.err 文件。")
    print("- 可执行提示：若 worker 使用 Hermes 会话日志，请到 Hermes 配置的 sessions/logs 目录按 run_id 或任务编号检索；若使用自定义脚本，请将短生命周期日志输出到工作区 logs/ 目录后再运行本脚本。")

print("\n【建议下一步】")
print(f"- {suggest_next_step(task, runs, events)}")
print("- 若信息不足，可增加数量后重跑：KANBAN_INSPECT_RUN_LIMIT=20 KANBAN_INSPECT_EVENT_LIMIT=50 scripts/readonly_task_log_inspector.sh " + TASK_ID)
print("- 本脚本全程使用 SQLite 只读连接 mode=ro，不会修改任务状态、不会杀进程、不会启动长驻服务。")

con.close()
PY
