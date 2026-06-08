from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import upsert_workspace_task_item
from backend.worker_recommendations import upsert_queue_worker

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def _client(tmp_path: Path) -> TestClient:
    """Create a test client using an isolated SQLite database.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Test client bound to the FastAPI app.
    """
    database.init_db(tmp_path / 'priority-router.db')
    return TestClient(app, raise_server_exceptions=False)


def test_priority_router_prefers_low_load_matching_worker(tmp_path: Path) -> None:
    """Priority router should select matching active worker with the lowest load."""
    client = _client(tmp_path)
    upsert_queue_worker('backend-busy', '繁忙后端', 'active', ['backend', 'FastAPI', 'SQLite'])
    upsert_queue_worker('backend-idle', '空闲后端', 'active', ['backend', 'FastAPI'])
    upsert_queue_worker('frontend-idle', '空闲前端', 'active', ['frontend', 'UI'])
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='running-1',
        title='后端接口一',
        status='running',
        description='后端接口开发',
        assignee='backend-busy',
        priority=10,
    )
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='running-2',
        title='后端接口二',
        status='running',
        description='后端接口开发',
        assignee='backend-busy',
        priority=9,
    )

    response = client.post(
        '/api/v1/workers/priority-router',
        json={
            'task_key': 'new-api-task',
            'title': '实现后端 API 端点',
            'description': '使用 FastAPI 和 SQLite 实现接口',
            'priority': 8,
            'workspace_path': str(WORKSPACE_ROOT),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已完成优先级分配'
    assert payload['data']['selected_worker']['worker_key'] == 'backend-idle'
    assert payload['data']['task_type'] == 'backend'
    assert payload['data']['board_summary']['running_tasks'] == 2
    assert payload['data']['candidates'][0]['load']['running_tasks'] == 0
    assert any('低负载优先' in item for item in payload['data']['decision_log'])


def test_priority_router_returns_structured_error_when_no_active_worker(tmp_path: Path) -> None:
    """Priority router should return a public structured error without DB details."""
    client = _client(tmp_path)
    upsert_queue_worker('disabled-backend', '停用后端', 'disabled', ['backend'])

    response = client.post(
        '/api/v1/workers/priority-router',
        json={
            'task_key': 'new-api-task',
            'title': '实现后端 API 端点',
            'description': '使用 FastAPI 和 SQLite 实现接口',
            'workspace_path': str(WORKSPACE_ROOT),
        },
    )

    assert response.status_code == 404
    assert response.json() == {'detail': '暂无可分配的 active worker'}
