from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import upsert_workspace_task_item
from backend.worker_board import build_worker_board

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def _client(tmp_path: Path) -> TestClient:
    """Create a test client with an isolated database.

    Args:
        tmp_path: Temporary directory from pytest.

    Returns:
        FastAPI test client.
    """
    db_path = tmp_path / 'tasks.db'
    database.init_db(db_path)
    with database.connect(db_path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS workspace_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace TEXT NOT NULL,
                task_key TEXT NOT NULL,
                task_id TEXT,
                parent_task_id TEXT,
                title TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('todo', 'ready', 'running', 'blocked', 'done', 'archived')),
                assignee TEXT,
                priority INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT NOT NULL DEFAULT '{}',
                UNIQUE(workspace, task_key)
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS task_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace TEXT NOT NULL,
                task_id TEXT NOT NULL,
                blocked_count INTEGER NOT NULL DEFAULT 0,
                last_failure_reason TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                last_accepted_at TEXT,
                health_level TEXT NOT NULL DEFAULT 'healthy',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(workspace, task_id)
            )"""
        )
    return TestClient(app, raise_server_exceptions=False)


def _leader_headers(client: TestClient) -> dict[str, str]:
    """Create a leader token for privileged API calls.

    Args:
        client: FastAPI test client.

    Returns:
        Authorization header dictionary.
    """
    phone = f'15550003001-{id(client)}'
    with database.connect() as connection:
        row = connection.execute('SELECT id FROM members WHERE phone = ?', (phone,)).fetchone()
    if row is None:
        leader = client.post(
            '/api/v1/auth/register',
            json={'name': 'Leader', 'phone': phone, 'password': 'secret123', 'role': 'member'},
        )
        assert leader.status_code == 201
        leader_id = leader.json()['data']['member']['id']
        with database.connect() as connection:
            connection.execute('UPDATE members SET role = ? WHERE id = ?', ('leader', leader_id))
    token = client.post('/api/v1/auth/login', json={'phone': phone, 'password': 'secret123'}).json()['data']['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_worker_board_helper_reports_idle_and_busy_workers() -> None:
    """Worker board helper should separate idle and busy workers.

    Returns:
        None.
    """
    db_path = Path(WORKSPACE_ROOT) / 'tmp-worker-board-helper.db'
    if db_path.exists():
        db_path.unlink()
    database.init_db(db_path)
    with database.connect(db_path) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS task_queue_workers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_key TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                capabilities TEXT NOT NULL DEFAULT '[]',
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS workspace_tasks (
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
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS task_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace TEXT NOT NULL,
                task_id TEXT NOT NULL,
                blocked_count INTEGER NOT NULL DEFAULT 0,
                last_failure_reason TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                last_accepted_at TEXT,
                health_level TEXT NOT NULL DEFAULT 'healthy',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(workspace, task_id)
            )"""
        )
        connection.execute(
            'INSERT INTO task_queue_workers (worker_key, name, status, capabilities) VALUES (?, ?, ?, ?)',
            ('worker-1', '后端工人', 'active', '["FastAPI"]'),
        )
        connection.execute(
            'INSERT INTO task_queue_workers (worker_key, name, status, capabilities) VALUES (?, ?, ?, ?)',
            ('worker-2', '前端工人', 'paused', '["UI"]'),
        )
        connection.execute(
            'INSERT INTO workspace_tasks (workspace, task_key, title, status, assignee, priority, updated_at, metadata, task_id, parent_task_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (str(WORKSPACE_ROOT), 'task-1', '实现任务看板', 'running', 'worker-1', 5, '2026-06-07T07:10:00+00:00', '{}', None, None),
        )
    snapshot = build_worker_board(WORKSPACE_ROOT)
    assert 'summary' in snapshot
    assert snapshot['summary']['busy_workers'] == 1
    assert snapshot['summary']['assigned_tasks'] == 1
    assert snapshot['summary']['running'] == 1


def test_worker_dashboard_endpoint_returns_api_response_shape(tmp_path, monkeypatch) -> None:
    """Worker board endpoint should return ApiResponse data and message fields.

    Args:
        tmp_path: Temporary directory from pytest.
        monkeypatch: Pytest environment patch helper.
    """
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))
    client = _client(tmp_path)
    headers = _leader_headers(client)

    client.post(
        '/api/v1/workers/intake',
        json={'worker_key': 'worker-001', 'name': '后端工人', 'status': 'active', 'capabilities': ['api', 'sqlite']},
        headers=headers,
    )
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='task-backend',
        title='实现后端任务分流',
        status='doing',
        description='后端负责创建和分流任务卡片',
        assignee='后端工人',
        priority=8,
        metadata={'lane': 'backend'},
    )

    response = client.get(
        '/api/v1/workers/board',
        params={'workspace_path': str(WORKSPACE_ROOT)},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert 'data' in payload and 'summary' in payload['data']
    assert 'summary' in payload['data']
    assert payload['data']['workspace_path'] == str(WORKSPACE_ROOT.resolve())


def test_worker_dashboard_summary_endpoint_includes_updated_at_and_workers(tmp_path, monkeypatch) -> None:
    """Worker dashboard summary endpoint should expose status counts and timestamps.

    Args:
        tmp_path: Temporary directory from pytest.
        monkeypatch: Pytest environment patch helper.
    """
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))
    client = _client(tmp_path)
    headers = _leader_headers(client)

    client.post(
        '/api/v1/workers/intake',
        json={'worker_key': 'worker-001', 'name': '后端工人', 'status': 'active', 'capabilities': ['api', 'sqlite']},
        headers=headers,
    )
    client.post(
        '/api/v1/workers/intake',
        json={'worker_key': 'worker-002', 'name': '前端工人', 'status': 'paused', 'capabilities': ['ui']},
        headers=headers,
    )
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='task-backend',
        title='实现后端任务分流',
        status='running',
        description='后端负责创建和分流任务卡片',
        assignee='后端工人',
        priority=8,
        metadata={'lane': 'backend'},
    )
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='task-frontend',
        title='实现前端任务看板',
        status='ready',
        description='前端负责展示任务板与筛选按钮',
        assignee='前端工人',
        priority=6,
        metadata={'lane': 'frontend'},
    )

    response = client.get(
        '/api/v1/dashboard/digest/summary',
        params={'workspace_path': str(WORKSPACE_ROOT)},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已返回空闲度概览面板'
    assert payload['data']['workspace_path'] == str(WORKSPACE_ROOT.resolve())
    assert payload['data']['summary']['worker_count'] == 2
    assert payload['data']['summary']['updated_at']
    assert payload['data']['summary']['ready'] == 1
    assert payload['data']['summary']['running'] == 1
    assert len(payload['data']['workers']) == 2
    assert isinstance(payload['data']['highlighted_workers'], list)
