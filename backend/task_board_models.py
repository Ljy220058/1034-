from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .database import connect, init_db
from .db import initialize_database
from .repository import (
    list_workspace_task_items as repository_list_workspace_task_items,
    list_workspace_tasks as repository_list_workspace_tasks,
)

RECENT_TASK_LIMIT = 20
RECENT_WORKSPACE_TASK_LIMIT = 10
TASK_LANE_KEYWORDS: dict[str, tuple[str, ...]] = {
    'test': ('测试', '校验', '验收', '回归', 'test', 'qa'),
    'review': ('审核', 'review', '评审', '审批', 'code review'),
    'frontend': ('前端', 'ui', '界面', '页面', 'frontend'),
    'backend': ('后端', 'api', 'sqlite', 'database', 'fastapi', 'backend'),
}
TASK_LANE_LABELS: dict[str, str] = {
    'test': '测试 worker',
    'review': '审核 worker',
    'frontend': '前端 worker',
    'backend': '后端 worker',
}


@dataclass(frozen=True)
class WorkerBoardSnapshot:
    """Worker board snapshot payload."""

    workspace_path: str
    idle_workers: list[dict[str, Any]]
    busy_workers: list[dict[str, Any]]
    assigned_tasks: list[dict[str, Any]]
    recent_tasks: list[dict[str, Any]]
    generated_at: str

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        return {
            'workspace_path': self.workspace_path,
            'idle_workers': self.idle_workers,
            'busy_workers': self.busy_workers,
            'assigned_tasks': self.assigned_tasks,
            'recent_tasks': self.recent_tasks,
            'generated_at': self.generated_at,
            'summary': {
                'idle_workers': len(self.idle_workers),
                'busy_workers': len(self.busy_workers),
                'assigned_tasks': len(self.assigned_tasks),
                'recent_tasks': len(self.recent_tasks),
            },
        }


@dataclass(frozen=True)
class TaskHealthRow:
    """Task health record used by the worker board."""

    task_id: str
    workspace: str
    health_level: str
    blocked_count: int
    retry_count: int
    last_failure_reason: str | None
    last_accepted_at: str | None
    updated_at: str
    created_at: str

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        return {
            'task_id': self.task_id,
            'workspace': self.workspace,
            'health_level': self.health_level,
            'blocked_count': self.blocked_count,
            'retry_count': self.retry_count,
            'last_failure_reason': self.last_failure_reason,
            'last_accepted_at': self.last_accepted_at,
            'updated_at': self.updated_at,
            'created_at': self.created_at,
        }


@dataclass(frozen=True)
class TaskRecommendation:
    """Recommended lane for a workspace task."""

    task_key: str
    title: str
    status: str
    recommended_lane: str
    recommended_assignee: str
    reason: str
    score: int
    matched_keywords: list[str]
    fallback: bool

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        return {
            'task_key': self.task_key,
            'title': self.title,
            'status': self.status,
            'recommended_lane': self.recommended_lane,
            'recommended_assignee': self.recommended_assignee,
            'reason': self.reason,
            'score': self.score,
            'matched_keywords': self.matched_keywords,
            'fallback': self.fallback,
        }


def _normalize_workspace_path(workspace_path: str | Path) -> str:
    return str(Path(workspace_path).expanduser().resolve())


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _decode_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _decode_json_dict(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {'raw': raw}
    return parsed if isinstance(parsed, dict) else {'value': parsed}


def _ensure_schema() -> None:
    initialize_database()
    init_db()
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS task_queue_workers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_key TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('active', 'paused', 'disabled')),
                capabilities TEXT NOT NULL DEFAULT '[]',
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace TEXT NOT NULL,
                task_key TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('todo', 'ready', 'running', 'blocked', 'done', 'archived')),
                assignee TEXT,
                priority INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT NOT NULL DEFAULT '{}',
                task_id TEXT,
                parent_task_id TEXT,
                UNIQUE(workspace, task_key)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS task_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace TEXT NOT NULL,
                task_id TEXT NOT NULL,
                blocked_count INTEGER NOT NULL DEFAULT 0 CHECK (blocked_count >= 0),
                last_failure_reason TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
                last_accepted_at TEXT,
                health_level TEXT NOT NULL DEFAULT 'healthy' CHECK (health_level IN ('healthy', 'at_risk', 'blocked', 'failing')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_task_health_workspace_task UNIQUE (workspace, task_id)
            )
            """
        )


def _row_to_worker(row: Any) -> dict[str, Any]:
    return {
        'id': row['id'],
        'worker_key': row['worker_key'],
        'name': row['name'],
        'status': row['status'],
        'capabilities': _decode_json_list(row['capabilities']),
        'last_seen_at': _parse_datetime(row['last_seen_at']).isoformat(),
        'created_at': _parse_datetime(row['created_at']).isoformat(),
        'updated_at': _parse_datetime(row['updated_at']).isoformat(),
    }


def _row_to_task_health(row: Any) -> TaskHealthRow:
    return TaskHealthRow(
        task_id=str(row['task_id']),
        workspace=str(row['workspace']),
        health_level=str(row['health_level']),
        blocked_count=int(row['blocked_count'] or 0),
        retry_count=int(row['retry_count'] or 0),
        last_failure_reason=row['last_failure_reason'],
        last_accepted_at=row['last_accepted_at'],
        updated_at=_parse_datetime(row['updated_at']).isoformat(),
        created_at=_parse_datetime(row['created_at']).isoformat(),
    )


def _row_to_workspace_task_item(row: Any) -> dict[str, Any]:
    metadata = _decode_json_dict(row['metadata'])
    return {
        'id': row['id'],
        'workspace': row['workspace'],
        'task_key': str(row['task_key']),
        'title': str(row['title']),
        'status': str(row['status']),
        'assignee': row['assignee'],
        'priority': int(row['priority'] or 0),
        'updated_at': _parse_datetime(row['updated_at']).isoformat(),
        'metadata': metadata,
        'task_id': row['task_id'] if 'task_id' in row.keys() else None,
        'parent_task_id': row['parent_task_id'] if 'parent_task_id' in row.keys() else None,
        'description': str(metadata.get('description', '')),
    }


def upsert_task_queue_worker(*, worker_key: str, name: str, status: str = 'active', capabilities: list[str] | None = None) -> dict[str, Any]:
    _ensure_schema()
    if status not in {'active', 'paused', 'disabled'}:
        raise ValueError('invalid worker status')
    capabilities_json = json.dumps(capabilities or [], ensure_ascii=False)
    with connect() as connection:
        existing = connection.execute('SELECT id FROM task_queue_workers WHERE worker_key = ?', (worker_key,)).fetchone()
        if existing is None:
            cursor = connection.execute(
                'INSERT INTO task_queue_workers(worker_key, name, status, capabilities) VALUES (?, ?, ?, ?)',
                (worker_key, name, status, capabilities_json),
            )
            worker_id = cursor.lastrowid
        else:
            connection.execute(
                'UPDATE task_queue_workers SET name = ?, status = ?, capabilities = ?, last_seen_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE worker_key = ?',
                (name, status, capabilities_json, worker_key),
            )
            worker_id = existing['id']
        row = connection.execute('SELECT * FROM task_queue_workers WHERE id = ?', (worker_id,)).fetchone()
    return _row_to_worker(row)


def list_task_queue_worker_records() -> list[dict[str, Any]]:
    _ensure_schema()
    with connect() as connection:
        rows = connection.execute('SELECT * FROM task_queue_workers ORDER BY updated_at DESC, id DESC').fetchall()
    return [_row_to_worker(row) for row in rows]


def list_queue_workers() -> list[dict[str, Any]]:
    return list_task_queue_worker_records()


def ensure_task_board_schema() -> None:
    """Ensure task board tables exist.

    Returns:
        None.
    """
    _ensure_schema()


def list_workspace_task_items(workspace_path: str | Path, *, limit: int = RECENT_WORKSPACE_TASK_LIMIT) -> list[dict[str, Any]]:
    _ensure_schema()
    normalized_workspace = _normalize_workspace_path(workspace_path)
    with connect() as connection:
        rows = connection.execute(
            'SELECT id, workspace, task_key, title, status, assignee, priority, updated_at, metadata, task_id, parent_task_id FROM workspace_tasks WHERE workspace = ? ORDER BY priority DESC, datetime(updated_at) DESC, id DESC LIMIT ?',
            (normalized_workspace, limit),
        ).fetchall()
    return [_row_to_workspace_task_item(row) for row in rows]


def list_workspace_tasks(workspace_path: str | Path, *, limit: int = RECENT_TASK_LIMIT) -> list[dict[str, Any]]:
    return list_workspace_task_items(workspace_path, limit=limit)


def upsert_workspace_task_item(*, workspace_path: str | Path, task_key: str, title: str, status: str, description: str, assignee: str | None, priority: int = 0, metadata: dict[str, Any] | None = None, task_id: str | None = None, parent_task_id: str | None = None) -> dict[str, Any]:
    _ensure_schema()
    normalized_workspace = _normalize_workspace_path(workspace_path)
    metadata_payload = dict(metadata or {})
    if description:
        metadata_payload.setdefault('description', description)
    metadata_json = json.dumps(metadata_payload, ensure_ascii=False)
    with connect() as connection:
        existing = connection.execute('SELECT id FROM workspace_tasks WHERE workspace = ? AND task_key = ?', (normalized_workspace, task_key)).fetchone()
        if existing is None:
            cursor = connection.execute(
                'INSERT INTO workspace_tasks(workspace, task_key, title, status, assignee, priority, metadata, task_id, parent_task_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (normalized_workspace, task_key, title, status, assignee, priority, metadata_json, task_id, parent_task_id),
            )
            row_id = cursor.lastrowid
        else:
            connection.execute(
                'UPDATE workspace_tasks SET title = ?, status = ?, assignee = ?, priority = ?, metadata = ?, task_id = ?, parent_task_id = ?, updated_at = CURRENT_TIMESTAMP WHERE workspace = ? AND task_key = ?',
                (title, status, assignee, priority, metadata_json, task_id, parent_task_id, normalized_workspace, task_key),
            )
            row_id = existing['id']
        row = connection.execute('SELECT id, workspace, task_key, title, status, assignee, priority, updated_at, metadata, task_id, parent_task_id FROM workspace_tasks WHERE id = ?', (row_id,)).fetchone()
    return _row_to_workspace_task_item(row)


def list_task_health_rows(workspace_path: str | Path, *, limit: int = 20) -> list[dict[str, Any]]:
    _ensure_schema()
    normalized_workspace = _normalize_workspace_path(workspace_path)
    with connect() as connection:
        rows = connection.execute(
            'SELECT workspace, task_id, blocked_count, last_failure_reason, retry_count, last_accepted_at, health_level, created_at, updated_at FROM task_health WHERE workspace = ? ORDER BY datetime(updated_at) DESC, id DESC LIMIT ?',
            (normalized_workspace, limit),
        ).fetchall()
    records = [_row_to_task_health(row) for row in rows]
    return [record.model_dump(mode='json') for record in records]


def list_workspace_task_items_for_recommendation(workspace_path: str | Path, *, limit: int = RECENT_WORKSPACE_TASK_LIMIT, status_filter: str | None = None, assignee: str | None = None) -> list[dict[str, Any]]:
    _ensure_schema()
    normalized_workspace = _normalize_workspace_path(workspace_path)
    params: list[Any] = [normalized_workspace]
    conditions = ['workspace = ?']
    if status_filter is not None:
        if status_filter not in {'todo', 'ready', 'running', 'blocked', 'done', 'archived'}:
            raise ValueError('invalid status filter')
        conditions.append('status = ?')
        params.append(status_filter)
    if assignee is not None:
        conditions.append('assignee = ?')
        params.append(assignee)
    params.append(limit)
    query = f"SELECT id, workspace, task_key, title, status, assignee, priority, updated_at, metadata, task_id, parent_task_id FROM workspace_tasks WHERE {' AND '.join(conditions)} ORDER BY priority DESC, datetime(updated_at) DESC, id DESC LIMIT ?"
    with connect() as connection:
        rows = connection.execute(query, params).fetchall()
    return [_row_to_workspace_task_item(row) for row in rows]


def build_worker_board_snapshot(workspace_path: str | Path) -> WorkerBoardSnapshot:
    _ensure_schema()
    workspace = _normalize_workspace_path(workspace_path)
    with connect() as connection:
        workers = connection.execute('SELECT * FROM task_queue_workers ORDER BY id ASC').fetchall()
        tasks = repository_list_workspace_tasks(workspace, limit=RECENT_WORKSPACE_TASK_LIMIT)
        assigned_tasks = repository_list_workspace_task_items(workspace, limit=RECENT_TASK_LIMIT)
    idle_workers = [_row_to_worker(row) for row in workers if row['status'] == 'active']
    busy_workers = []
    return WorkerBoardSnapshot(
        workspace_path=workspace,
        idle_workers=idle_workers,
        busy_workers=busy_workers,
        assigned_tasks=assigned_tasks,
        recent_tasks=tasks,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def recommend_worker_for_task(title: str, description: str = '', capabilities: list[str] | None = None) -> dict[str, Any]:
    text = f'{title} {description}'.lower()
    lowered_capabilities = [cap.lower() for cap in (capabilities or [])]
    for lane, keywords in TASK_LANE_KEYWORDS.items():
        matched_keywords = [keyword for keyword in keywords if keyword.lower() in text]
        if matched_keywords:
            assignee = TASK_LANE_LABELS[lane]
            reason = f'标题或描述包含{assignee.split(" ", 1)[0]}语义，优先分配{assignee}'
            return {
                'recommended_lane': lane,
                'reason': reason,
                'matched_keywords': matched_keywords,
                'score': 90 + len(matched_keywords) * 5,
                'fallback': False,
            }
    if any(keyword in lowered_capabilities for keyword in ('test', 'qa', '测试')):
        return {
            'recommended_lane': 'test',
            'reason': '能力标签提示测试方向，优先分配测试 worker',
            'matched_keywords': ['capabilities:test'],
            'score': 80,
            'fallback': False,
        }
    if any(keyword in lowered_capabilities for keyword in ('review', '审核', '评审')):
        return {
            'recommended_lane': 'review',
            'reason': '能力标签提示审核方向，优先分配审核 worker',
            'matched_keywords': ['capabilities:review'],
            'score': 80,
            'fallback': False,
        }
    return {
        'recommended_lane': 'backend',
        'reason': '默认按后端实现优先处理，便于继续扩展规则',
        'matched_keywords': [],
        'score': 50,
        'fallback': True,
    }
