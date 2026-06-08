from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .database import connect, init_db
from .repository import ensure_workspace_tasks_table


@dataclass(frozen=True)
class WorkspaceTask:
    task_id: str
    title: str
    status: str
    updated_at: datetime
    assignee: str | None
    workspace_path: str | None
    parent_task_id: str | None
    metadata: dict[str, Any]

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        return {
            'task_id': self.task_id,
            'title': self.title,
            'status': self.status,
            'updated_at': self.updated_at.isoformat(),
            'assignee': self.assignee,
            'workspace_path': self.workspace_path,
            'parent_task_id': self.parent_task_id,
            'metadata': self.metadata,
        }


def _normalize_workspace_path(workspace_path: str | Path) -> str:
    return str(Path(workspace_path).expanduser().resolve())


def _decode_metadata(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {'value': parsed}
    except Exception:
        return {'raw': raw}


def _row_to_task(row: sqlite3.Row) -> WorkspaceTask:
    updated_at = datetime.fromisoformat(row['last_seen_at'])
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return WorkspaceTask(
        task_id=row['task_id'],
        title=row['title'],
        status=row['status'],
        updated_at=updated_at,
        assignee=row['assignee'],
        workspace_path=row['workspace_path'],
        parent_task_id=row['parent_task_id'],
        metadata=_decode_metadata(row['metadata']),
    )


def ensure_task_discovery_schema() -> None:
    ensure_workspace_tasks_table()
    init_db()
    with connect() as connection:
        existing_columns = {row['name'] for row in connection.execute("PRAGMA table_info(task_queue_workers)").fetchall()}
        if 'workspace_path' not in existing_columns:
            connection.execute('ALTER TABLE task_queue_workers ADD COLUMN workspace_path TEXT')
        if 'task_id' not in existing_columns:
            connection.execute('ALTER TABLE task_queue_workers ADD COLUMN task_id TEXT')
        if 'parent_task_id' not in existing_columns:
            connection.execute('ALTER TABLE task_queue_workers ADD COLUMN parent_task_id TEXT')
        if 'metadata' not in existing_columns:
            connection.execute('ALTER TABLE task_queue_workers ADD COLUMN metadata TEXT')
        try:
            connection.execute('CREATE INDEX IF NOT EXISTS idx_task_queue_workers_workspace_status_updated ON task_queue_workers(workspace_path, status, updated_at DESC, id DESC)')
        except Exception:
            pass


def upsert_workspace_task(*, task_id: str, title: str, status: str, updated_at: datetime | None = None, assignee: str | None = None, workspace_path: str | Path | None = None, parent_task_id: str | None = None, metadata: dict[str, Any] | None = None) -> None:
    ensure_task_discovery_schema()
    timestamp = updated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    normalized_workspace = _normalize_workspace_path(workspace_path) if workspace_path is not None else None
    with connect() as connection:
        connection.execute(
            '''
            INSERT INTO task_queue_workers(worker_key, name, status, capabilities, last_seen_at, created_at, updated_at, workspace_path, task_id, parent_task_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(worker_key) DO UPDATE SET
                name = excluded.name,
                status = excluded.status,
                capabilities = excluded.capabilities,
                last_seen_at = excluded.last_seen_at,
                updated_at = excluded.updated_at,
                workspace_path = excluded.workspace_path,
                task_id = excluded.task_id,
                parent_task_id = excluded.parent_task_id,
                metadata = excluded.metadata
            ''',
            (
                task_id,
                title,
                status,
                json.dumps(sorted(metadata.get('capabilities', [])) if metadata else [], ensure_ascii=False),
                timestamp.isoformat(),
                timestamp.isoformat(),
                timestamp.isoformat(),
                normalized_workspace,
                task_id,
                parent_task_id,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )


def create_task_payloads() -> list[dict]:
    """Create default kanban task payloads for creative task flows.

    Returns:
        List of task payload dicts.
    """
    return [
        {
            'task_key': 'creative-task-001',
            'title': '生成活动创意',
            'status': 'todo',
            'description': '自动生成社群活动创意任务',
            'assignee': None,
            'priority': 5,
        },
        {
            'task_key': 'creative-task-002',
            'title': '审核活动方案',
            'status': 'todo',
            'description': '审核并优化自动生成的活动方案',
            'assignee': None,
            'priority': 4,
        },
    ]



def list_workspace_tasks(workspace_path: str | Path, *, limit: int = 100, status_filter: str | None = None) -> list[WorkspaceTask]:
    ensure_task_discovery_schema()
    if limit < 1 or limit > 500:
        raise ValueError('limit must be between 1 and 500')
    normalized_workspace = _normalize_workspace_path(workspace_path)
    params: list[Any] = [normalized_workspace]
    status_clause = ''
    if status_filter is not None:
        allowed_statuses = {'todo', 'running', 'done', 'blocked', 'ready', 'archived'}
        if status_filter not in allowed_statuses:
            raise ValueError('invalid status filter')
        status_clause = ' AND status = ?'
        params.append(status_filter)
    params.append(limit)
    query = f'''
        SELECT task_id, title, status, last_seen_at, assignee, workspace_path, parent_task_id, metadata
        FROM task_queue_workers
        WHERE workspace_path = ?{status_clause}
        ORDER BY datetime(last_seen_at) DESC, id DESC
        LIMIT ?
    '''
    with connect() as connection:
        rows = connection.execute(query, params).fetchall()
    return [_row_to_task(row) for row in rows]
