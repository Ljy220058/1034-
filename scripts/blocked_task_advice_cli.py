#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.blocked_task_advice import build_blocked_task_advice  # noqa: E402

BLOCKED_STATUSES = {"blocked", "triage"}

COMMON_REASON_HINTS: list[tuple[tuple[str, ...], str]] = [
    (
        ("缺少测试", "测试结果", "pytest", "test", "验证结果"),
        "请先运行最小相关测试并把命令、通过/失败结果、关键错误粘贴到评论；如果失败可自行修复，修完继续推进，不用等待人工确认。",
    ),
    (
        ("接口契约", "契约不清", "字段", "schema", "api", "请求", "响应"),
        "请把当前理解的请求/响应字段、示例 payload、兼容性假设写清楚；按最小可用契约先实现并补充验证，后续差异再迭代。",
    ),
    (
        ("依赖任务", "父任务", "parent", "dependency", "依赖", "未完成"),
        "先检查父任务/依赖任务状态：若依赖确实未完成，只保留依赖关系不要强行解锁；若只是信息缺口，用现有评论和产物继续推进并说明假设。",
    ),
    (
        ("工作区", "workspace", "路径", "目录", "不存在", "无法进入", "permission", "权限"),
        "请先验证工作区路径是否存在且可写；路径异常时在正确项目目录重建最小工作区，记录实际路径后继续执行。",
    ),
]


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)


def _read_json_source(source: str) -> Any:
    if source == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(source).read_text(encoding="utf-8")
    if not raw.strip():
        return []
    return json.loads(raw)


def _extract_tasks(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("tasks", "items", "data", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if "task" in payload and isinstance(payload["task"], dict):
            return [payload["task"]]
        if any(key in payload for key in ("id", "task_id", "status", "title")):
            return [payload]
    raise SystemExit("输入 JSON 必须是任务列表，或包含 tasks/items/data/rows 的对象。")


def _task_status(task: dict[str, Any]) -> str:
    return _stringify(task.get("status")).lower()


def _reason_text(task: dict[str, Any], advice: dict[str, Any]) -> str:
    evidence_value = advice.get("evidence")
    evidence = evidence_value if isinstance(evidence_value, dict) else {}
    sections_value = advice.get("sections")
    sections = sections_value if isinstance(sections_value, dict) else {}
    pieces = [
        task.get("block_reason"),
        task.get("blocked_reason"),
        task.get("failure_reason"),
        task.get("last_failure_reason"),
        task.get("result"),
        evidence.get("block_reason"),
        sections.get("可能原因"),
        task.get("title"),
    ]
    return " ".join(_stringify(piece) for piece in pieces if _stringify(piece)).lower()


def _common_action(task: dict[str, Any], advice: dict[str, Any]) -> str:
    text = _reason_text(task, advice)
    for tokens, action in COMMON_REASON_HINTS:
        if any(token.lower() in text for token in tokens):
            return action
    return "请先复现最近一次阻塞线索，能自行补齐的信息直接补齐；遇到错误自己修，不用等人。若确实需要外部凭证或产品取舍，再把最小问题写成评论。"


def _format_one(task: dict[str, Any]) -> str:
    advice = build_blocked_task_advice(task)
    sections = advice.get("sections", {})
    task_id = advice.get("task_id") or _stringify(task.get("id")) or "未知任务"
    title = advice.get("title") or "未命名任务"
    status = advice.get("status") or _task_status(task)
    assignee = advice.get("assignee") or "未指定负责人"
    workspace = advice.get("workspace") or "未记录工作区"
    common_action = _common_action(task, advice)

    comment = (
        f"任务阻塞自动解除建议：\n"
        f"- 当前判断：{sections.get('可能原因', '未记录阻塞原因')}\n"
        f"- 建议操作：{common_action}\n"
        f"- 执行人：{assignee}\n"
        f"- 工作区：{workspace}\n"
        f"- 备注：继续干，遇到错误自己修，不用等人。"
    )
    return (
        f"【任务 {task_id}】{title}\n"
        f"状态：{status}\n"
        f"可复制到看板评论：\n{comment}"
    )


def build_output(tasks: Iterable[dict[str, Any]]) -> str:
    blocked_tasks = [task for task in tasks if _task_status(task) in BLOCKED_STATUSES]
    if not blocked_tasks:
        return "当前没有需要解除阻塞的任务。blocked/triage 任务数：0。"
    return "\n\n---\n\n".join(_format_one(task) for task in blocked_tasks)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从看板快照 JSON 生成可复制到看板评论的中文阻塞解除建议。"
    )
    parser.add_argument(
        "--from-json",
        default="-",
        metavar="PATH|-",
        help="任务快照 JSON 文件路径；使用 - 从 stdin 读取。JSON 可为任务数组或包含 tasks/items/data/rows 的对象。",
    )
    parser.add_argument(
        "--example",
        action="store_true",
        help="输出内置示例快照的建议，便于快速查看格式。",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.example:
        payload: Any = [
            {"id": "t_running", "title": "正常运行", "status": "running", "assignee": "worker-a"},
            {"id": "t_blocked", "title": "缺少测试结果", "status": "blocked", "assignee": "qa-worker", "block_reason": "缺少测试结果。"},
            {"id": "t_contract", "title": "接口契约不清", "status": "blocked", "assignee": "backend-dev", "block_reason": "接口契约不清。"},
        ]
    else:
        payload = _read_json_source(args.from_json)
    print(build_output(_extract_tasks(payload)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
