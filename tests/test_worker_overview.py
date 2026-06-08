from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import upsert_workspace_task_item

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
            '''CREATE TABLE IF NOT EXISTS workspace_tasks (
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
            )'''
        )
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS task_health (
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
            )'''
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


def _seed_worker_board(client: TestClient, headers: dict[str, str]) -> None:
    """Seed worker and task board data for overview tests.

    Args:
        client: FastAPI test client.
        headers: Auth headers for privileged endpoints.
    """
    client.post(
        '/api/v1/workers/intake',
        json={'worker_key': 'worker-001', 'name': '后端工人', 'status': 'active', 'capabilities': ['api', 'sqlite']},
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
        metadata={'lane': 'backend', 'retry_hint': '自动重试'},
    )
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='task-review',
        title='任务分流代码评审',
        status='blocked',
        description='等待人工复核',
        assignee=None,
        priority=3,
        metadata={'lane': 'review', 'needs_retry': True},
    )


def test_worker_board_endpoint_returns_chinese_summary_and_counts(tmp_path, monkeypatch) -> None:
    """Worker board should expose Chinese labels and health counts.

    Args:
        tmp_path: Temporary directory from pytest.
        monkeypatch: Pytest environment patch helper.
    """
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))
    client = _client(tmp_path)
    headers = _leader_headers(client)
    _seed_worker_board(client, headers)

    response = client.get(
        '/api/v1/workers/board',
        params={'workspace_path': str(WORKSPACE_ROOT)},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert 'message' in body
    assert 'summary' in body['data']
    assert 'workers' in body['data']
    assert 'idle_workers' in body['data']


def test_worker_summary_endpoint_includes_health_counts(tmp_path, monkeypatch) -> None:
    """Worker summary should expose task counts and health counts.

    Args:
        tmp_path: Temporary directory from pytest.
        monkeypatch: Pytest environment patch helper.
    """
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))
    client = _client(tmp_path)
    headers = _leader_headers(client)
    _seed_worker_board(client, headers)

    response = client.get('/api/v1/workers/summary', headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert 'message' in payload
    assert payload['data']['task_counts'].get('running', 0) + payload['data']['task_counts'].get('blocked', 0) >= 1
    assert 'health_counts' in payload['data']
    assert 'worker_counts' in payload['data']
    assert 'copy_hint' in payload['data']


def test_worker_recommendations_endpoint_returns_summary(tmp_path, monkeypatch) -> None:
    """Recommendation endpoint should return a summary field.

    Args:
        tmp_path: Temporary directory from pytest.
        monkeypatch: Pytest environment patch helper.
    """
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))
    client = _client(tmp_path)
    headers = _leader_headers(client)
    _seed_worker_board(client, headers)
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='test-task',
        title='补充回归测试',
        status='todo',
        description='校验接口返回格式',
        assignee=None,
        priority=10,
        metadata={'lane': 'test'},
    )

    response = client.get(
        '/api/v1/workers/idle-recommendations',
        params={'workspace_path': str(WORKSPACE_ROOT), 'limit': 5},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert 'message' in payload
    assert 'recommendations' in payload['data']
    if payload['data']['recommendations']:
        recommendation = payload['data']['recommendations'][0]
        assert 'task_key' in recommendation or 'title' in recommendation
