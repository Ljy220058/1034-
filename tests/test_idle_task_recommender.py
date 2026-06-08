from __future__ import annotations

from pathlib import Path

import backend.database as database
from backend.app import app
from fastapi.testclient import TestClient


class _FakeUser:
    role = 'leader'


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
    client = TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
    from backend.routes import common

    app.dependency_overrides[common.get_current_user] = lambda: _FakeUser()
    return client


def test_idle_backend_summary_endpoint_returns_api_response_shape(tmp_path: Path) -> None:
    """空闲后端摘要接口应返回 ApiResponse 结构。"""
    client = _client(tmp_path)

    response = client.get('/api/v1/idle-backend-summary')

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已生成空闲后端任务摘要'
    assert 'data' in payload and 'summary' in payload['data']


def test_idle_backend_task_recommender_endpoint_returns_api_response_shape(tmp_path: Path) -> None:
    """空闲后端推荐接口应返回 ApiResponse 结构。"""
    client = _client(tmp_path)

    response = client.get('/api/v1/idle-backend-task-recommender')

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert 'recommendations' in payload['data']
