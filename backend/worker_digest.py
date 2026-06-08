from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from .database import connect
from .worker_recommendations import build_worker_board, list_queue_workers

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def normalize_worker_digest_workspace(workspace_path: str) -> str:
    """Normalize a workspace selector to an absolute path.

    Args:
        workspace_path: Raw workspace selector string.

    Returns:
        Normalized absolute workspace path.

    Raises:
        HTTPException: When the workspace selector is invalid.
    """
    normalized = workspace_path.strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='工作区参数不合法')
    if normalized.startswith('dir:'):
        normalized = normalized.removeprefix('dir:')
    if normalized.startswith('worktree:'):
        normalized = normalized.removeprefix('worktree:')
    if normalized.startswith('scratch:'):
        normalized = normalized.removeprefix('scratch:')
    if not normalized.startswith('/'):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='工作区参数不合法')
    return normalized.rstrip('/') or normalized


def default_worker_digest_workspace(workspace_path: str | None) -> str:
    """Return a normalized workspace path for dashboard endpoints.

    Args:
        workspace_path: Optional query workspace path.

    Returns:
        Absolute workspace path.
    """
    if workspace_path is None or not workspace_path.strip():
        return str(PROJECT_ROOT)
    return normalize_worker_digest_workspace(workspace_path)


def _ensure_digest_schema() -> None:
    """Ensure dashboard digest tables exist."""
    with connect() as connection:
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
                UNIQUE (workspace, task_id)
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
                status TEXT NOT NULL,
                assignee TEXT,
                priority INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT NOT NULL DEFAULT '{}',
                task_id TEXT,
                parent_task_id TEXT,
                UNIQUE (workspace, task_key)
            )
            """
        )


def _health_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a health row to response payload.

    Args:
        row: SQLite task_health row.

    Returns:
        JSON-ready health row.
    """
    return {
        'task_id': row['task_id'],
        'workspace': row['workspace'],
        'health_level': row['health_level'],
        'blocked_count': int(row['blocked_count'] or 0),
        'retry_count': int(row['retry_count'] or 0),
        'last_failure_reason': row['last_failure_reason'],
        'last_accepted_at': row['last_accepted_at'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


def _count_task_statuses(workspace_path: str) -> dict[str, int]:
    """Count workspace tasks by status.

    Args:
        workspace_path: Workspace path filter.

    Returns:
        Status count mapping.
    """
    with connect() as connection:
        rows = connection.execute(
            'SELECT status, COUNT(*) AS total FROM workspace_tasks WHERE workspace = ? GROUP BY status',
            (workspace_path,),
        ).fetchall()
    return {str(row['status']): int(row['total']) for row in rows}


def _count_health_levels(workspace_path: str) -> dict[str, int]:
    """Count task health rows by level.

    Args:
        workspace_path: Workspace path filter.

    Returns:
        Health level count mapping.
    """
    with connect() as connection:
        rows = connection.execute(
            'SELECT health_level, COUNT(*) AS total FROM task_health WHERE workspace = ? GROUP BY health_level',
            (workspace_path,),
        ).fetchall()
    return {str(row['health_level']): int(row['total']) for row in rows}


def _list_health_rows(workspace_path: str, *, alerts_only: bool = False, limit: int = 20) -> list[dict[str, Any]]:
    """List health rows for dashboard summaries.

    Args:
        workspace_path: Workspace path filter.
        alerts_only: Whether to return only repeated warnings.
        limit: Maximum row count.

    Returns:
        Health rows ordered by severity.
    """
    if alerts_only:
        sql = """
            SELECT workspace, task_id, blocked_count, last_failure_reason, retry_count,
                   last_accepted_at, health_level, created_at, updated_at
            FROM task_health
            WHERE workspace = ? AND (blocked_count > 0 OR retry_count > 0 OR health_level IN ('blocked', 'failing'))
            ORDER BY blocked_count DESC, retry_count DESC, datetime(updated_at) DESC, id DESC
            LIMIT ?
        """
    else:
        sql = """
            SELECT workspace, task_id, blocked_count, last_failure_reason, retry_count,
                   last_accepted_at, health_level, created_at, updated_at
            FROM task_health
            WHERE workspace = ?
            ORDER BY blocked_count DESC, retry_count DESC, datetime(updated_at) DESC, id DESC
            LIMIT ?
        """
    with connect() as connection:
        rows = connection.execute(sql, (workspace_path, limit)).fetchall()
    return [_health_row_to_dict(row) for row in rows]


def _build_summary_text(idle_count: int, todo_count: int, running_count: int, alert_count: int) -> str:
    """Build Chinese dashboard summary text.

    Args:
        idle_count: Idle worker count.
        todo_count: Todo task count.
        running_count: Running task count.
        alert_count: Duplicate alert count.

    Returns:
        Chinese summary string for frontend display.
    """
    return f'当前有 {idle_count} 个空闲 worker，{todo_count} 个待办任务，{running_count} 个运行中任务，{alert_count} 条重复告警。'


def build_worker_digest_payload(workspace_path: str, *, include_health: bool = True) -> dict[str, Any]:
    """Build worker dashboard digest data.

    Args:
        workspace_path: Normalized workspace path.
        include_health: Whether to include health and alert rows.

    Returns:
        Aggregated worker dashboard digest payload.

    Raises:
        HTTPException: Database read failed.
    """
    try:
        snapshot = build_worker_board(workspace_path)
        _ensure_digest_schema()
        workers = list_queue_workers()
        task_counts = _count_task_statuses(workspace_path)
        health_counts = _count_health_levels(workspace_path)
        health_rows = _list_health_rows(workspace_path, limit=20) if include_health else []
        alerts = _list_health_rows(workspace_path, alerts_only=True, limit=20) if include_health else []
    except sqlite3.Error as exc:
        logger.exception('failed to build worker dashboard digest')
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='读取 worker 摘要失败') from exc

    summary_snapshot = snapshot.get('summary', {}) if isinstance(snapshot, dict) else {}
    idle_count = int(summary_snapshot.get('idle_workers') or summary_snapshot.get('idle_worker_count') or 0)
    busy_count = int(summary_snapshot.get('busy_workers') or summary_snapshot.get('busy_worker_count') or 0)
    todo_count = task_counts.get('todo', 0) + task_counts.get('ready', 0)
    running_count = task_counts.get('running', 0) + task_counts.get('doing', 0)
    return {
        'workspace_path': workspace_path,
        'summary_text': _build_summary_text(idle_count, todo_count, running_count, len(alerts)),
        'copy_hint': '点击 worker 名称即可复制可分配 worker 名称',
        'summary': {
            'worker_count': len(workers),
            'idle_worker_count': idle_count,
            'ready': todo_count,
            'running': running_count,
            'blocked': task_counts.get('blocked', 0),
            'done': task_counts.get('done', 0),
            'duplicate_task_keys': [],
            'todo_task_count': todo_count,
            'running_task_count': running_count,
            'duplicate_alert_count': len(alerts),
            'task_health_count': len(health_rows),
        },
        'worker_counts': {'total': len(workers), 'idle': idle_count, 'busy': busy_count},
        'task_counts': task_counts,
        'health_counts': health_counts,
        'snapshot': snapshot,
        'health_rows': health_rows,
        'alerts': alerts,
    }
