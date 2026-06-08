from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .database import connect, init_db
from .db import initialize_database
from .repository import (
    list_workspace_task_items as repository_list_workspace_task_items,
    list_workspace_tasks as repository_list_workspace_tasks,
    upsert_workspace_task_item as repository_upsert_workspace_task_item,
)

RECENT_TASK_LIMIT = 20
RECENT_WORKSPACE_TASK_LIMIT = 10


@dataclass(frozen=True)
class WorkerBoardSnapshot:
    """Worker board snapshot payload.

    Attributes:
        workspace_path: Normalized workspace path.
        idle_workers: Workers that are active and have no running tasks.
        busy_workers: Workers that are active and currently handling tasks.
        assigned_tasks: Tasks assigned to known workers.
        recent_tasks: Most recent workspace tasks.
        generated_at: Snapshot generation timestamp.
    """

    workspace_path: str
    idle_workers: list[dict[str, Any]]
    busy_workers: list[dict[str, Any]]
    assigned_tasks: list[dict[str, Any]]
    recent_tasks: list[dict[str, Any]]
    generated_at: str

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        """Serialize the snapshot to a JSON-ready dictionary.

        Args:
            mode: Serialization mode, kept for API compatibility.

        Returns:
            JSON-ready snapshot payload.
        """
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
        """Serialize task health row.

        Args:
            mode: Serialization mode, kept for API compatibility.

        Returns:
            JSON-ready task health payload.
        """
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


def _normalize_workspace_path(workspace_path: str | Path) -> str:
    """Normalize a workspace path.

    Args:
        workspace_path: Workspace path from API or caller.

    Returns:
        Absolute normalized workspace path.
    """
    return str(Path(workspace_path).expanduser().resolve())


def _parse_datetime(value: str) -> datetime:
    """Parse database datetime text.

    Args:
        value: ISO datetime text.

    Returns:
        Timezone-aware datetime.
    """
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _decode_json_list(raw: str | None) -> list[str]:
    """Decode JSON list safely.

    Args:
        raw: JSON text from SQLite.

    Returns:
        String list.
    """
    if not raw:
        return []
    import json

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _decode_json_dict(raw: str | None) -> dict[str, Any]:
    """Decode JSON dictionary safely.

    Args:
        raw: JSON text from SQLite.

    Returns:
        Dictionary payload.
    """
    if not raw:
        return {}
    import json

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {'raw': raw}
    return parsed if isinstance(parsed, dict) else {'value': parsed}


def _ensure_schema() -> None:
    """Ensure worker board tables exist."""
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
    """Convert a worker row to a JSON-ready dictionary."""
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
    """Convert a task health row to a dataclass."""
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


def upsert_task_queue_worker(*, worker_key: str, name: str, status: str = 'active', capabilities: list[str] | None = None) -> dict[str, Any]:
    """Create or update a task queue worker.

    Args:
        worker_key: Stable worker identifier.
        name: Human-readable worker name.
        status: Worker lifecycle status.
        capabilities: Optional worker capability tags.

    Returns:
        JSON-ready worker record.
    """
    _ensure_schema()
    caps = json.dumps(list(capabilities or []), ensure_ascii=False)
    with connect() as connection:
        row = connection.execute('SELECT * FROM task_queue_workers WHERE worker_key = ?', (worker_key,)).fetchone()
        if row is None:
            cursor = connection.execute(
                'INSERT INTO task_queue_workers (worker_key, name, status, capabilities) VALUES (?, ?, ?, ?)',
                (worker_key, name, status, caps),
            )
            row = connection.execute('SELECT * FROM task_queue_workers WHERE id = ?', (cursor.lastrowid,)).fetchone()
        else:
            connection.execute(
                'UPDATE task_queue_workers SET name = ?, status = ?, capabilities = ?, updated_at = CURRENT_TIMESTAMP WHERE worker_key = ?',
                (name, status, caps, worker_key),
            )
            row = connection.execute('SELECT * FROM task_queue_workers WHERE worker_key = ?', (worker_key,)).fetchone()
    return _row_to_worker(row)


def create_task_queue_worker(worker_key: str, name: str, status: str = 'active', capabilities: list[str] | None = None) -> tuple[dict[str, Any], str]:
    """Compatibility wrapper returning the worker record and action.

    Args:
        worker_key: Stable worker identifier.
        name: Human-readable worker name.
        status: Worker lifecycle status.
        capabilities: Optional worker capability tags.

    Returns:
        Tuple of worker record and action label.
    """
    return upsert_task_queue_worker(worker_key=worker_key, name=name, status=status, capabilities=capabilities), 'upserted'


def list_task_queue_workers() -> list[dict[str, Any]]:
    """List task queue workers.

    Returns:
        JSON-ready worker list.
    """
    _ensure_schema()
    with connect() as connection:
        rows = connection.execute('SELECT * FROM task_queue_workers ORDER BY id ASC').fetchall()
    return [_row_to_worker(row) for row in rows]


def upsert_task_health(*, workspace_path: str | Path, task_id: str, health_level: str, blocked_count: int = 0, retry_count: int = 0, last_failure_reason: str | None = None, last_accepted_at: datetime | str | None = None) -> TaskHealthRow:
    """Create or update a task health record.

    Args:
        workspace_path: Workspace path.
        task_id: Task identifier.
        health_level: Health classification.
        blocked_count: Number of blocks.
        retry_count: Number of retries.
        last_failure_reason: Latest failure reason.
        last_accepted_at: Latest accepted timestamp.

    Returns:
        Task health row.
    """
    _ensure_schema()
    workspace = _normalize_workspace_path(workspace_path)
    accepted_at = last_accepted_at.isoformat() if isinstance(last_accepted_at, datetime) else last_accepted_at
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO task_health (
                workspace, task_id, blocked_count, retry_count, last_failure_reason, last_accepted_at, health_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(workspace, task_id) DO UPDATE SET
                blocked_count = excluded.blocked_count,
                retry_count = excluded.retry_count,
                last_failure_reason = excluded.last_failure_reason,
                last_accepted_at = excluded.last_accepted_at,
                health_level = excluded.health_level,
                updated_at = CURRENT_TIMESTAMP
            """,
            (workspace, task_id, blocked_count, retry_count, last_failure_reason, accepted_at, health_level),
        )
        row = connection.execute('SELECT * FROM task_health WHERE workspace = ? AND task_id = ?', (workspace, task_id)).fetchone()
    return _row_to_task_health(row)


def list_task_health_rows(workspace_path: str | Path) -> list[dict[str, Any]]:
    """List task health rows for a workspace.

    Args:
        workspace_path: Workspace path.

    Returns:
        JSON-ready task health rows.
    """
    _ensure_schema()
    workspace = _normalize_workspace_path(workspace_path)
    with connect() as connection:
        rows = connection.execute('SELECT * FROM task_health WHERE workspace = ? ORDER BY updated_at DESC, id DESC', (workspace,)).fetchall()
    return [row.model_dump(mode='json') for row in map(_row_to_task_health, rows)]


def build_task_health_summary(workspace_path: str | Path) -> dict[str, Any]:
    """Build a task health summary for a workspace.

    Args:
        workspace_path: Workspace path.

    Returns:
        Summary dictionary.
    """
    rows = list_task_health_rows(workspace_path)
    counts = {'ready': 0, 'running': 0, 'blocked': 0, 'done': 0}
    return {
        'workspace_path': _normalize_workspace_path(workspace_path),
        'counts': counts,
        'total': len(rows),
        'recent_tasks': rows,
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }


def list_workspace_task_health(*, workspace_path: str | Path, health_level: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """List task health records, optionally filtered by health level.

    Args:
        workspace_path: Workspace directory path.
        health_level: Optional health level filter.
        limit: Maximum records to return.

    Returns:
        List of task health dicts.
    """
    _ensure_schema()
    normalized = _normalize_workspace_path(workspace_path)
    with connect() as connection:
        if health_level:
            rows = connection.execute(
                "SELECT * FROM task_health WHERE workspace = ? AND health_level = ? ORDER BY updated_at DESC, id DESC LIMIT ?",
                (normalized, health_level, limit),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM task_health WHERE workspace = ? ORDER BY updated_at DESC, id DESC LIMIT ?",
                (normalized, limit),
            ).fetchall()
    return [_row_to_task_health(row) for row in rows]


def get_task_health_by_task_id(*, workspace_path: str | Path, task_id: str) -> dict[str, Any] | None:
    """Read one task health record by workspace and task id.

    Args:
        workspace_path: Workspace directory path.
        task_id: Stable task identifier.

    Returns:
        Task health dictionary, or None when no record exists.
    """
    _ensure_schema()
    normalized = _normalize_workspace_path(workspace_path)
    with connect() as connection:
        row = connection.execute(
            'SELECT * FROM task_health WHERE workspace = ? AND task_id = ?',
            (normalized, task_id),
        ).fetchone()
    return _row_to_task_health(row).model_dump(mode='json') if row is not None else None


def upsert_workspace_task_item(
    *,
    workspace_path: str | Path,
    task_key: str,
    title: str,
    status: str,
    description: str = '',
    assignee: str | None = None,
    priority: int = 0,
    metadata: dict[str, Any] | None = None,
    task_id: str | None = None,
    parent_task_id: str | None = None,
) -> dict[str, Any]:
    """Upsert a workspace task item through the repository layer.

    Args:
        workspace_path: Workspace directory path.
        task_key: Unique task key inside the workspace.
        title: Task title.
        status: Task status.
        description: Human-readable task description.
        assignee: Optional assignee.
        priority: Sort priority.
        metadata: Extra JSON metadata.
        task_id: Optional kanban task id.
        parent_task_id: Optional parent task id.

    Returns:
        JSON-ready task item dictionary.
    """
    return repository_upsert_workspace_task_item(
        workspace_path=workspace_path,
        task_key=task_key,
        title=title,
        status='running' if status == 'doing' else status,
        description=description,
        assignee=assignee,
        priority=priority,
        metadata=metadata,
        task_id=task_id,
        parent_task_id=parent_task_id,
    )


def build_worker_board(workspace_path: str | Path, *, refresh: bool = False) -> dict[str, Any]:
    """Build a worker board payload for workspace routes.

    Args:
        workspace_path: Workspace root path.
        refresh: Whether caller requested a fresh snapshot.

    Returns:
        JSON-ready worker board payload with summary counts.
    """
    _ensure_schema()
    workspace = _normalize_workspace_path(workspace_path)
    workers = list_task_queue_workers()
    tasks = repository_list_workspace_task_items(workspace, limit=RECENT_TASK_LIMIT)
    health_rows = list_task_health_rows(workspace)
    running_assignees = {str(task.get('assignee')) for task in tasks if task.get('assignee') and task.get('status') in {'running', 'doing'}}
    idle_workers = [worker for worker in workers if worker.get('status') == 'active' and worker.get('name') not in running_assignees and worker.get('worker_key') not in running_assignees]
    busy_workers = [worker for worker in workers if worker not in idle_workers]
    status_counts = {'待办': 0, '进行中': 0, '阻塞': 0, '完成': 0}
    for task in tasks:
        status = task.get('status')
        if status in {'todo', 'ready'}:
            status_counts['待办'] += 1
        elif status in {'running', 'doing'}:
            status_counts['进行中'] += 1
        elif status == 'blocked':
            status_counts['阻塞'] += 1
        elif status == 'done':
            status_counts['完成'] += 1
    health_counts = {'healthy': 0, 'at_risk': 0, 'blocked': 0, 'failing': 0}
    for row in health_rows:
        level = row.get('health_level') if isinstance(row, dict) else getattr(row, 'health_level', None)
        if level in health_counts:
            health_counts[str(level)] += 1
    return {
        'workspace_path': workspace,
        'refresh': refresh,
        'summary': {
            'idle_workers': len(idle_workers),
            'busy_workers': len(busy_workers),
            'assigned_tasks': sum(1 for task in tasks if task.get('assignee')),
            'recent_changes': len(tasks),
            'running': status_counts['进行中'],
            'blocked': status_counts['阻塞'],
        },
        'idle_workers': idle_workers,
        'busy_workers': busy_workers,
        'assigned_tasks': [task for task in tasks if task.get('assignee')],
        'recent_changes': tasks,
        'status_counts': status_counts,
        'health_counts': health_counts,
    }


def build_worker_board_snapshot(workspace_path: str | Path) -> WorkerBoardSnapshot:
    """Build a worker board snapshot."""
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
        assigned_tasks=[task.model_dump(mode='json') if hasattr(task, 'model_dump') else dict(task) for task in assigned_tasks],
        recent_tasks=[task.model_dump(mode='json') if hasattr(task, 'model_dump') else dict(task) for task in tasks],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
