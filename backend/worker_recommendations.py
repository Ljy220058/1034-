from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .database import connect, init_db
from .db import initialize_database
from .worker_board import build_worker_board

WORKER_STATUSES = {'active', 'paused', 'disabled'}
RUNNING_TASK_STATUSES = {'running', 'doing'}
EXECUTABLE_TASK_STATUSES = {'todo', 'ready'}
WORKSPACE_TASK_STATUSES = {'todo', 'ready', 'running', 'doing', 'blocked', 'done', 'archived'}


@dataclass(frozen=True)
class QueueWorker:
    """Task queue worker persisted in SQLite."""

    id: int
    worker_key: str
    name: str
    status: str
    capabilities: list[str]
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        """Serialize worker data.

        Args:
            mode: Serialization mode, kept for compatibility.

        Returns:
            JSON-ready worker payload.
        """
        return {
            'id': self.id,
            'worker_key': self.worker_key,
            'name': self.name,
            'status': self.status,
            'capabilities': self.capabilities,
            'last_seen_at': self.last_seen_at.isoformat(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


@dataclass(frozen=True)
class WorkspaceQueueTask:
    """Workspace task row used for worker recommendations."""

    task_id: str
    title: str
    status: str
    assignee: str | None
    priority: int
    updated_at: datetime
    metadata: dict[str, Any]

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        """Serialize workspace task data.

        Args:
            mode: Serialization mode, kept for compatibility.

        Returns:
            JSON-ready task payload.
        """
        return {
            'task_id': self.task_id,
            'title': self.title,
            'status': self.status,
            'assignee': self.assignee,
            'priority': self.priority,
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata,
        }


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _decode_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _decode_metadata(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {'raw': raw}
    return parsed if isinstance(parsed, dict) else {'value': parsed}


def _normalize_workspace_path(workspace_path: str | Path) -> str:
    """Normalize a workspace path to an absolute string.

    Args:
        workspace_path: Workspace root path.

    Returns:
        Absolute normalized workspace path.
    """
    return str(Path(workspace_path).expanduser().resolve())


def default_worker_digest_workspace(workspace_path: str | Path) -> str:
    """Return the normalized workspace path for worker digest use.

    Args:
        workspace_path: Workspace root path.

    Returns:
        Normalized absolute workspace path.
    """
    return _normalize_workspace_path(workspace_path)


def ensure_queue_schema() -> None:
    """Ensure worker and workspace task tables have the expected shape."""
    initialize_database()
    init_db()
    with connect() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS workspace_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace TEXT NOT NULL,
                task_key TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                assignee TEXT,
                priority INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT NOT NULL DEFAULT '{}',
                task_id TEXT,
                parent_task_id TEXT,
                UNIQUE(workspace, task_key)
            )
            '''
        )
        columns = {row['name'] for row in connection.execute('PRAGMA table_info(workspace_tasks)').fetchall()}
        if 'task_id' not in columns:
            connection.execute('ALTER TABLE workspace_tasks ADD COLUMN task_id TEXT')
        if 'parent_task_id' not in columns:
            connection.execute('ALTER TABLE workspace_tasks ADD COLUMN parent_task_id TEXT')
        if 'metadata' not in columns:
            connection.execute('ALTER TABLE workspace_tasks ADD COLUMN metadata TEXT NOT NULL DEFAULT "{}"')


def _row_to_worker(row: sqlite3.Row) -> QueueWorker:
    return QueueWorker(
        id=row['id'],
        worker_key=row['worker_key'],
        name=row['name'],
        status=row['status'],
        capabilities=_decode_json_list(row['capabilities']),
        last_seen_at=_parse_dt(row['last_seen_at']),
        created_at=_parse_dt(row['created_at']),
        updated_at=_parse_dt(row['updated_at']),
    )


def _row_to_task(row: sqlite3.Row) -> WorkspaceQueueTask:
    return WorkspaceQueueTask(
        task_id=row['task_id'] or row['task_key'],
        title=row['title'],
        status=row['status'],
        assignee=row['assignee'],
        priority=int(row['priority'] or 0),
        updated_at=_parse_dt(row['updated_at']),
        metadata=_decode_metadata(row['metadata']),
    )


def upsert_queue_worker(worker_key: str, name: str, status: str, capabilities: list[str]) -> tuple[QueueWorker, str]:
    """Create or update a task queue worker.

    Args:
        worker_key: Stable worker identifier.
        name: Human-readable worker name.
        status: Worker status.
        capabilities: Capability labels.

    Returns:
        Worker and persistence action, either ``created`` or ``updated``.

    Raises:
        ValueError: Status is invalid.
    """
    ensure_queue_schema()
    if status not in WORKER_STATUSES:
        raise ValueError('invalid worker status')
    capabilities_json = json.dumps(capabilities, ensure_ascii=False)
    with connect() as connection:
        existing = connection.execute('SELECT id FROM task_queue_workers WHERE worker_key = ?', (worker_key,)).fetchone()
        if existing is None:
            cursor = connection.execute(
                'INSERT INTO task_queue_workers(worker_key, name, status, capabilities) VALUES (?, ?, ?, ?)',
                (worker_key, name, status, capabilities_json),
            )
            worker_id = cursor.lastrowid
            action = 'created'
        else:
            connection.execute(
                'UPDATE task_queue_workers SET name = ?, status = ?, capabilities = ?, last_seen_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE worker_key = ?',
                (name, status, capabilities_json, worker_key),
            )
            worker_id = existing['id']
            action = 'updated'
        row = connection.execute('SELECT * FROM task_queue_workers WHERE id = ?', (worker_id,)).fetchone()
    return _row_to_worker(row), action


def list_queue_workers() -> list[QueueWorker]:
    """List known task queue workers."""
    ensure_queue_schema()
    with connect() as connection:
        rows = connection.execute('SELECT * FROM task_queue_workers ORDER BY updated_at DESC, id DESC').fetchall()
    return [_row_to_worker(row) for row in rows]



def recommend_worker_for_task(
    title: str,
    description: str = "",
    capabilities: list[str] | None = None,
) -> dict[str, Any]:
    """Recommend a worker lane for a given task.

    Args:
        title: Task title.
        description: Optional task description.
        capabilities: Optional list of required capabilities.

    Returns:
        Dict with recommended_lane and reason keys.
    """
    text = f"{title} {description}".lower()
    # Simple keyword-based lane routing
    if any(kw in text for kw in ("fix", "修复", "bug", "error", "syntax", "import")):
        lane = "backend-dev"
        reason = "修复类任务，需要后端开发能力"
    elif any(kw in text for kw in ("frontend", "前端", "ui", "css", "页面")):
        lane = "frontend-dev"
        reason = "前端开发任务"
    elif any(kw in text for kw in ("test", "测试", "pytest", "smoke")):
        lane = "test-engineer"
        reason = "测试类任务"
    elif any(kw in text for kw in ("security", "安全", "auth", "token")):
        lane = "security-auditor"
        reason = "安全审计类任务"
    elif any(kw in text for kw in ("docs", "文档", "readme", "doc")):
        lane = "docs-writer"
        reason = "文档类任务"
    elif any(kw in text for kw in ("deploy", "部署", "ci", "cd", "devops")):
        lane = "devops-engineer"
        reason = "运维类任务"
    elif capabilities:
        lane = capabilities[0] if "backend" in str(capabilities).lower() else "backend-dev"
        reason = f"基于能力匹配: {capabilities[0]}"
    else:
        lane = "backend-dev"
        reason = "默认分配至后端开发"
    return {"recommended_lane": lane, "reason": reason}


# Alias for backward compatibility
def build_worker_recommendations(workspace_path: str | Path) -> dict[str, Any]:
    """Build worker routing recommendations.

    Args:
        workspace_path: Workspace root path.

    Returns:
        API payload containing ranked worker recommendations.
    """
    board = build_worker_board(workspace_path)
    board_data = board.model_dump(mode='json') if hasattr(board, 'model_dump') else dict(board)
    workers = board_data.get('idle_workers', []) + board_data.get('busy_workers', [])
    recommendations = []
    for worker in workers:
        if not isinstance(worker, dict):
            continue
        worker_key = str(worker.get('worker_key') or '').strip()
        running_tasks = sum(
            1
            for task in board_data.get('recent_tasks', [])
            if isinstance(task, dict)
            and str(task.get('assignee') or '').strip() == worker_key
            and str(task.get('status')) in RUNNING_TASK_STATUSES
        )
        recommendations.append(
            {
                'worker_key': worker_key,
                'name': str(worker.get('name') or '').strip(),
                'status': worker.get('status'),
                'capabilities': list(worker.get('capabilities') or []),
                'running_tasks': running_tasks,
                'score': max(0, 100 - running_tasks * 20),
            }
        )
    recommendations.sort(key=lambda item: (-int(item['score']), str(item['worker_key'])))
    return {
        'workspace_path': _normalize_workspace_path(workspace_path),
        'recommendations': recommendations,
        'summary': {
            'worker_count': len(recommendations),
            'recommended_count': len(recommendations),
        },
    }


def list_queue_tasks(workspace_path: str | Path, *, limit: int = 100) -> list[WorkspaceQueueTask]:
    """List workspace tasks for recommendation snapshots.

    Args:
        workspace_path: Workspace root path.
        limit: Maximum rows to return.

    Returns:
        Workspace tasks ordered by priority and update time.
    """
    ensure_queue_schema()
    normalized_workspace = _normalize_workspace_path(workspace_path)
    with connect() as connection:
        rows = connection.execute(
            'SELECT task_key, task_id, title, status, assignee, priority, updated_at, metadata FROM workspace_tasks WHERE workspace = ? ORDER BY priority DESC, datetime(updated_at) DESC, id DESC LIMIT ?',
            (normalized_workspace, limit),
        ).fetchall()
    return [_row_to_task(row) for row in rows]

def build_worker_board(workspace_path: str | Path, *, worker_filter: str | None = None, refresh: bool = False) -> dict[str, Any]:
    """Build a compact worker board snapshot.

    Args:
        workspace_path: Workspace root path.
        worker_filter: Optional worker key filter.
        refresh: Whether caller requested a fresh snapshot.

    Returns:
        Stable Chinese API payload.
    """
    workers = list_queue_workers()
    tasks = list_queue_tasks(workspace_path, limit=200)
    running_assignees = set()
    selected_workers = [worker for worker in workers if worker_filter is None or worker.worker_key == worker_filter]
    idle_workers = [worker for worker in selected_workers if worker.status == 'active' and worker.worker_key not in running_assignees]
    assigned_tasks = [task for task in tasks if task.assignee and (worker_filter is None or task.assignee == worker_filter)]
    recent_changes = tasks[:5]
    return {
        'workspace_path': _normalize_workspace_path(workspace_path),
        'worker_filter': worker_filter,
        'refresh': refresh,
        'summary': {
            'worker_count': len(selected_workers),
            'active_worker_count': sum(1 for worker in selected_workers if worker.status == 'active'),
            'task_count': len(tasks),
            'running_task_count': sum(1 for task in tasks if task.status in RUNNING_TASK_STATUSES),
            'dispatchable_task_count': sum(1 for task in tasks if task.status in EXECUTABLE_TASK_STATUSES),
        },
        'workers': [worker.model_dump(mode='json') for worker in selected_workers],
        'idle_workers': [worker.model_dump(mode='json') for worker in idle_workers],
        'busy_workers': [worker.model_dump(mode='json') for worker in selected_workers if worker not in idle_workers],
        'tasks': [task.model_dump(mode='json') for task in tasks],
        'assigned_tasks': [task.model_dump(mode='json') for task in assigned_tasks],
        'recent_changes': [task.model_dump(mode='json') for task in recent_changes],
    }

# Backward-compatible alias for test imports
worker_recommendations = build_worker_recommendations
