from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .database import DB_PATH, connect, init_db
from .db import initialize_database

RECENT_TASK_LIMIT = 20
RECENT_WORKSPACE_TASK_LIMIT = 10


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
class WorkspaceTaskItem:
    task_key: str
    title: str
    status: str
    assignee: str | None
    priority: int
    updated_at: str
    metadata: dict[str, Any]
    task_id: str | None = None
    parent_task_id: str | None = None
    description: str = ''

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        return {
            'task_key': self.task_key,
            'title': self.title,
            'status': self.status,
            'assignee': self.assignee,
            'priority': self.priority,
            'updated_at': self.updated_at,
            'metadata': self.metadata,
            'task_id': self.task_id,
            'parent_task_id': self.parent_task_id,
            'description': self.description,
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
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                start_time TEXT NOT NULL,
                location TEXT NOT NULL,
                route TEXT,
                distance_km REAL,
                pace_group TEXT,
                description TEXT,
                max_participants INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
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


def ensure_task_board_schema() -> None:
    _ensure_schema()


def _row_to_worker(row: sqlite3.Row) -> dict[str, Any]:
    return {
        'id': row['id'],
        'worker_key': row['worker_key'],
        'name': row['name'],
        'status': row['status'],
        'capabilities': _decode_json_list(row['capabilities']),
        'last_seen_at': row['last_seen_at'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


def _row_to_workspace_task_item(row: sqlite3.Row) -> WorkspaceTaskItem:
    metadata = _decode_json_dict(row['metadata'])
    return WorkspaceTaskItem(
        task_key=row['task_key'],
        title=row['title'],
        status=row['status'],
        assignee=row['assignee'],
        priority=row['priority'],
        updated_at=row['updated_at'],
        metadata=metadata,
        task_id=row['task_id'],
        parent_task_id=row['parent_task_id'],
        description=str(metadata.get('description', '')),
    )


def _row_to_task_health(row: sqlite3.Row) -> TaskHealthRow:
    return TaskHealthRow(
        task_id=row['task_id'],
        workspace=row['workspace'],
        health_level=row['health_level'],
        blocked_count=row['blocked_count'],
        retry_count=row['retry_count'],
        last_failure_reason=row['last_failure_reason'],
        last_accepted_at=row['last_accepted_at'],
        updated_at=row['updated_at'],
        created_at=row['created_at'],
    )


def _activity_row_to_model(row: sqlite3.Row) -> Any:
    from .models import ActivityOut

    return ActivityOut(
        id=row['id'],
        title=row['title'],
        start_time=row['start_time'],
        location=row['location'],
        route=row['route'],
        distance_km=row['distance_km'],
        pace_group=row['pace_group'],
        description=row['description'],
        max_participants=row['max_participants'],
        created_at=row['created_at'],
        updated_at=row['updated_at'],
    )


def create_activity(payload: Any) -> Any:
    from .models import ActivityCreate

    if not isinstance(payload, ActivityCreate):
        payload = ActivityCreate.model_validate(payload)
    _ensure_schema()
    with connect() as connection:
        cursor = connection.execute(
            '''
            INSERT INTO activities (title, start_time, location, route, distance_km, pace_group, description, max_participants)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                payload.title,
                payload.start_time.isoformat(),
                payload.location,
                payload.route,
                payload.distance_km,
                payload.pace_group,
                payload.description,
                payload.max_participants,
            ),
        )
        row = connection.execute('SELECT * FROM activities WHERE id = ?', (cursor.lastrowid,)).fetchone()
    return _activity_row_to_model(row)


def list_activities() -> list[Any]:
    _ensure_schema()
    with connect() as connection:
        rows = connection.execute('SELECT * FROM activities ORDER BY start_time DESC, id DESC').fetchall()
    return [_activity_row_to_model(row) for row in rows]


def create_task_queue_worker(worker_key: str, name: str, status: str, capabilities: list[str]) -> tuple[dict[str, Any], str]:
    _ensure_schema()
    capabilities_value = json.dumps(capabilities or [], ensure_ascii=False)
    with connect() as connection:
        existing = connection.execute('SELECT * FROM task_queue_workers WHERE worker_key = ?', (worker_key,)).fetchone()
        if existing is not None:
            connection.execute(
                'UPDATE task_queue_workers SET name = ?, status = ?, capabilities = ?, last_seen_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE worker_key = ?',
                (name, status, capabilities_value, worker_key),
            )
            row = connection.execute('SELECT * FROM task_queue_workers WHERE worker_key = ?', (worker_key,)).fetchone()
            return _row_to_worker(row), 'updated'
        cursor = connection.execute(
            'INSERT INTO task_queue_workers (worker_key, name, status, capabilities) VALUES (?, ?, ?, ?)',
            (worker_key, name, status, capabilities_value),
        )
        row = connection.execute('SELECT * FROM task_queue_workers WHERE id = ?', (cursor.lastrowid,)).fetchone()
        return _row_to_worker(row), 'created'


def list_task_queue_workers() -> list[dict[str, Any]]:
    _ensure_schema()
    with connect() as connection:
        rows = connection.execute('SELECT * FROM task_queue_workers ORDER BY updated_at DESC, id DESC').fetchall()
        return [_row_to_worker(row) for row in rows]


def ensure_workspace_tasks_table() -> None:
    """Ensure workspace task schema exists for task discovery modules."""
    _ensure_schema()


def get_activity(activity_id: int) -> Any:
    _ensure_schema()
    with connect() as connection:
        row = connection.execute('SELECT * FROM activities WHERE id = ?', (activity_id,)).fetchone()
    return None if row is None else _activity_row_to_model(row)


def update_activity(activity_id: int, payload: Any) -> Any:
    from .models import ActivityUpdate

    if not isinstance(payload, ActivityUpdate):
        payload = ActivityUpdate.model_validate(payload)
    existing = get_activity(activity_id)
    if existing is None:
        return None
    values = payload.model_dump(exclude_unset=True)
    if not values:
        return existing
    assignments: list[str] = []
    params: list[Any] = []
    for key, value in values.items():
        assignments.append(f'{key} = ?')
        params.append(value.isoformat() if isinstance(value, datetime) else value)
    params.append(activity_id)
    _ensure_schema()
    with connect() as connection:
        connection.execute(f'UPDATE activities SET {", ".join(assignments)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', params)
    return get_activity(activity_id)


def delete_activity(activity_id: int) -> bool:
    _ensure_schema()
    with connect() as connection:
        cursor = connection.execute('DELETE FROM activities WHERE id = ?', (activity_id,))
    return cursor.rowcount > 0


def create_registration(activity_id: int, member_id: int) -> tuple[Any, str]:
    return None, 'not_found'


def cancel_registration(activity_id: int, member_id: int) -> Any:
    return None


def get_member(member_id: int) -> Any:
    return None


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
    _ensure_schema()
    normalized_workspace = str(Path(workspace_path).expanduser().resolve())
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(metadata or {}, ensure_ascii=False)
    with connect() as connection:
        connection.execute(
            '''
            INSERT INTO workspace_tasks (
                workspace, task_key, title, status, assignee, priority, updated_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(workspace, task_key) DO UPDATE SET
                title = excluded.title,
                status = excluded.status,
                assignee = excluded.assignee,
                priority = excluded.priority,
                updated_at = excluded.updated_at,
                metadata = excluded.metadata
            ''',
            (normalized_workspace, task_key, title, status, assignee, priority, timestamp, payload),
        )
        row = connection.execute(
            '''
            SELECT workspace, task_key, title, status, assignee, priority, updated_at, metadata, task_id, parent_task_id
            FROM workspace_tasks
            WHERE workspace = ? AND task_key = ?
            ''',
            (normalized_workspace, task_key),
        ).fetchone()
    return _row_to_workspace_task_item(row).model_dump()


def list_workspace_task_items(workspace_path: str | Path, limit: int = RECENT_WORKSPACE_TASK_LIMIT, status_filter: str | None = None) -> list[dict[str, Any]]:
    _ensure_schema()
    normalized_workspace = _normalize_workspace_path(workspace_path)
    query = [
        'SELECT workspace, task_key, title, status, assignee, priority, updated_at, metadata, task_id, parent_task_id',
        'FROM workspace_tasks',
        'WHERE workspace = ?',
    ]
    params: list[Any] = [normalized_workspace]
    if status_filter is not None:
        query.append('AND status = ?')
        params.append(status_filter)
    query.append('ORDER BY updated_at DESC, id DESC LIMIT ?')
    params.append(limit)
    with connect() as connection:
        rows = connection.execute(' '.join(query), params).fetchall()
    return [_row_to_workspace_task_item(row).model_dump() for row in rows]


def list_workspace_tasks(workspace_path: str | Path, limit: int = RECENT_WORKSPACE_TASK_LIMIT, status_filter: str | None = None) -> list[WorkspaceTaskItem]:
    return [_row_to_workspace_task_item_from_dict(item) for item in list_workspace_task_items(workspace_path, limit=limit, status_filter=status_filter)]


def ensure_workspace_tasks_table() -> None:
    """Ensure workspace task table exists for discovery modules."""
    _ensure_schema()


def _row_to_workspace_task_item_from_dict(item: dict[str, Any]) -> WorkspaceTaskItem:
    return WorkspaceTaskItem(
        task_key=str(item['task_key']),
        title=str(item['title']),
        status=str(item['status']),
        assignee=item.get('assignee'),
        priority=int(item.get('priority', 0)),
        updated_at=str(item.get('updated_at', '')),
        metadata=item.get('metadata', {}) if isinstance(item.get('metadata', {}), dict) else {},
        task_id=item.get('task_id'),
        parent_task_id=item.get('parent_task_id'),
        description=str((item.get('metadata', {}) or {}).get('description', '')) if isinstance(item.get('metadata', {}), dict) else '',
    )

from . import basic_repository as _basic_repository
from .basic_repository import (
    create_announcement,
    create_member_with_password,
    delete_announcement,
    delete_member,
    get_announcement,
    get_member,
    list_announcements,
    list_members,
    update_announcement,
    update_member,
)

from .attendance import (
    create_attendance,
    delete_attendance,
    get_attendance,
    list_attendance as list_activity_attendance,
)

from .activity_registration_risk import (
    create_activity,
    create_registration,
    cancel_registration,
    delete_activity,
    get_activity,
    get_registration_status,
    list_activities,
    list_registration_statuses,
    registration_risk_smoke_panel,
    update_activity,
)

Member = _basic_repository.MemberRecord


def reset_database() -> None:
    """Reset the SQLite database to an empty initialized state."""
    if Path(DB_PATH).exists():
        Path(DB_PATH).unlink()
    init_db(DB_PATH)

def create_member(*args: Any, **kwargs: Any) -> Any:
    """Create a member using either legacy kwargs or a payload object.

    Args:
        args: Optional legacy connection plus payload object.
        kwargs: Legacy member fields.

    Returns:
        Member id for legacy calls, otherwise a member record.
    """
    if kwargs:
        connection = args[0] if args and hasattr(args[0], 'execute') else None
        fields = {
            'name': kwargs.get('name'),
            'phone': kwargs.get('phone'),
            'role': kwargs.get('role', 'member'),
            'running_years': int(kwargs.get('running_years') or 0),
            'pace': kwargs.get('pace'),
            'usual_distance_km': kwargs.get('usual_distance_km'),
            'training_goal': kwargs.get('training_goal'),
            'password_hash': kwargs.get('password_hash', ''),
        }
        sql = '''
            INSERT INTO members (name, phone, role, running_years, pace, usual_distance_km, training_goal, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            fields['name'],
            fields['phone'],
            fields['role'],
            fields['running_years'],
            fields['pace'],
            fields['usual_distance_km'],
            fields['training_goal'],
            fields['password_hash'],
        )
        if connection is not None:
            cursor = connection.execute(sql, params)
            return int(cursor.lastrowid)
        with connect() as new_connection:
            cursor = new_connection.execute(sql, params)
            return int(cursor.lastrowid)
