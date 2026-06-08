from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import upsert_workspace_task_item
from backend.worker_recommendations import upsert_queue_worker

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def _client(tmp_path: Path) -> TestClient:
    """Create a FastAPI client with an isolated database.

    Args:
        tmp_path: Temporary path provided by pytest.

    Returns:
        FastAPI test client bound to the app.
    """
    database.init_db(tmp_path / 'worker-routing.db')
    return TestClient(app, raise_server_exceptions=False)


def test_worker_board_endpoint_returns_structured_payload(tmp_path: Path, monkeypatch) -> None:
    """Worker board endpoint should expose routing-ready board data.

    Args:
        tmp_path: Temporary path provided by pytest.
        monkeypatch: Pytest environment helper.
    """
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))
    client = _client(tmp_path)
    upsert_queue_worker('backend-001', '后端工人', 'active', ['backend', 'FastAPI', 'SQLite'])
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='task-backend',
        title='实现后端路由提醒',
        status='running',
        description='后端 worker 需要感知新任务进入看板',
        assignee='backend-001',
        priority=8,
        metadata={'lane': 'backend'},
    )
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='task-review',
        title='评审路由规则',
        status='blocked',
        description='等待人工复核',
        assignee=None,
        priority=3,
        metadata={'lane': 'review'},
    )

    response = client.get('/api/v1/workers/board', params={'workspace_path': str(WORKSPACE_ROOT)})

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['summary']['idle_workers'] >= 0
    assert payload['data']['summary']['busy_workers'] >= 0
    assert payload['data']['snapshot']['workspace_path'] == str(WORKSPACE_ROOT)


def test_worker_summary_endpoint_exposes_copy_hint_and_counts(tmp_path: Path, monkeypatch) -> None:
    """Worker summary endpoint should expose compact counts for operator copy.

    Args:
        tmp_path: Temporary path provided by pytest.
        monkeypatch: Pytest environment helper.
    """
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))
    client = _client(tmp_path)
    upsert_queue_worker('backend-001', '后端工人', 'active', ['backend', 'FastAPI'])
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='task-backend',
        title='实现后端路由提醒',
        status='running',
        description='后端 worker 需要感知新任务进入看板',
        assignee='backend-001',
        priority=8,
        metadata={'lane': 'backend'},
    )

    response = client.get('/api/v1/workers/summary', params={'workspace_path': str(WORKSPACE_ROOT)})

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['workspace_path'] == str(WORKSPACE_ROOT)
    assert payload['data']['task_counts']['running'] == 1
    assert payload['data']['copy_hint'] == '点击 worker 名称即可复制可分配 worker 名称'
    assert isinstance(payload['data']['worker_counts'], dict)


def test_worker_priority_router_returns_chinese_structured_error_when_no_active_worker(tmp_path: Path) -> None:
    """Priority router should fail with a public Chinese error when no active worker exists.

    Args:
        tmp_path: Temporary path provided by pytest.
    """
    client = _client(tmp_path)
    upsert_queue_worker('disabled-backend', '停用后端', 'disabled', ['backend'])

    response = client.post(
        '/api/v1/workers/priority-router',
        json={
            'task_key': 'task-new',
            'title': '实现后端 API 端点',
            'description': '使用 FastAPI 和 SQLite 实现接口',
            'priority': 8,
            'workspace_path': str(WORKSPACE_ROOT),
        },
    )

    assert response.status_code == 404
    assert response.json() == {'detail': '暂无可分配的 active worker'}
