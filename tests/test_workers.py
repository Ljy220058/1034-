from __future__ import annotations

import sqlite3
from pathlib import Path

import backend.database as database
from fastapi.testclient import TestClient

from backend.app import app
from conftest import make_auth_headers

WORKSPACE_ROOT = '/root/autodl-tmp/projects/hermes-swarm-lab'


def _ensure_workspace_tasks_table(db_path: Path) -> None:
    """Create the workspace tasks table used by tests.

    Args:
        db_path: SQLite database path.
    """
    with sqlite3.connect(db_path) as connection:
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
                updated_at TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}'
            )
            '''
        )
        connection.commit()


def test_worker_intake_creates_and_lists_workers() -> None:
    """Worker intake endpoint should create and list structured workers."""
    client = TestClient(app, raise_server_exceptions=False)

    create_response = client.post(
        '/api/v1/workers/intake',
        json={
            'worker_key': 'backend-worker-a',
            'name': '后端 worker A',
            'status': 'active',
            'capabilities': ['FastAPI', 'SQLite'],
        },
        headers={'Authorization': make_auth_headers(client, '19900000001', 'member')['Authorization']},
    )
    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload['message'] in {'已创建 worker', '已更新 worker'}
    assert create_payload['data']['worker_key'] == 'backend-worker-a'

    list_response = client.get(
        '/api/v1/workers/intake',
        headers={'Authorization': make_auth_headers(client, '19900000001', 'member')['Authorization']},
    )
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert any(item['worker_key'] == 'backend-worker-a' for item in list_payload['data'])


def test_worker_allocate_prefers_best_matching_active_worker() -> None:
    """Worker allocation should prefer the best active worker by task type."""
    client = TestClient(app, raise_server_exceptions=False)

    client.post(
        '/api/v1/workers/intake',
        json={
            'worker_key': 'frontend-worker-b',
            'name': '前端 worker B',
            'status': 'active',
            'capabilities': ['React', 'UI'],
        },
        headers={'Authorization': make_auth_headers(client, '19900000001', 'member')['Authorization']},
    )
    client.post(
        '/api/v1/workers/intake',
        json={
            'worker_key': 'backend-worker-c',
            'name': '后端 worker C',
            'status': 'paused',
            'capabilities': ['FastAPI', 'SQLite'],
        },
        headers={'Authorization': make_auth_headers(client, '19900000001', 'member')['Authorization']},
    )

    response = client.post(
        '/api/v1/workers/allocate?title=%E5%BC%80%E5%8F%91%20API%20%E6%8E%A5%E5%8F%A3&description=FastAPI%20%E5%90%8E%E7%AB%AF%E4%B8%8E%20SQLite%20%E9%85%8D%E7%BD%AE',
        headers={'Authorization': make_auth_headers(client, '19900000001', 'member')['Authorization']},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已完成 worker 分流'
    assert payload['data']['assignee'] == 'backend-dev'
    assert payload['data']['task_type'] == 'backend'
    assert payload['data']['candidates'][0]['status'] == 'active'


def test_worker_board_endpoint_returns_api_response_shape() -> None:
    """Worker board endpoint should return ApiResponse data and message fields."""
    db_path = Path(WORKSPACE_ROOT) / 'tmp-worker-board-tests.db'
    if db_path.exists():
        db_path.unlink()
    database.init_db(db_path)
    _ensure_workspace_tasks_table(db_path)
    with database.connect(db_path) as connection:
        connection.execute(
            'INSERT INTO workspace_tasks (workspace, task_key, title, status, assignee, priority, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (WORKSPACE_ROOT, 'task-1', 'Alpha Task', 'running', 'backend-worker-a', 5, '2026-06-07T07:10:00+00:00', '{"tags": ["api"]}'),
        )
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(
        f'/api/v1/workers/board?workspace_path=dir:{WORKSPACE_ROOT}',
        headers={'Authorization': make_auth_headers(client, '19900000001', 'member')['Authorization']},
    )
    assert response.status_code == 200
    payload = response.json()
    assert 'data' in payload and 'message' in payload
    assert payload['message'] == '成功'
