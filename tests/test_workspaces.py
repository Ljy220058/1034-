from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.database import connect, init_db
from backend.models import TaskItemCreate
from backend.routes.common import CurrentUser, token_for_member

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Create an isolated database-backed FastAPI client."""
    db_path = tmp_path / 'workspaces.db'
    monkeypatch.setenv('RUNNING_CLUB_DB_PATH', str(db_path))
    init_db(db_path)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _auth_headers(role: str, member_id: int) -> dict[str, str]:
    """Build a signed bearer token for the requested role."""
    token = token_for_member(CurrentUser(id=member_id, role=role, member=None))
    return {'Authorization': f'Bearer {token}'}


@pytest.mark.parametrize(
    ('payload', 'status_code', 'detail'),
    [
        ({'workspace_path': str(WORKSPACE_ROOT), 'items': []}, 422, '任务列表不能为空'),
        ({'items': [{'task_key': 'task-001'}]}, 422, 'workspace_path 不能为空'),
    ],
)
def test_workspace_batch_create_rejects_invalid_payload(client: TestClient, payload: dict, status_code: int, detail: str) -> None:
    """批量创建工作区任务时，空列表和缺少 workspace_path 都会被拒绝。"""
    response = client.post('/api/v1/workspaces/tasks/items/batch', headers=_auth_headers('leader', 1), json=payload)

    assert response.status_code == status_code
    assert response.json()['detail'] == detail


def test_workspace_batch_create_requires_authentication(client: TestClient) -> None:
    """未携带 token 不能批量创建工作区任务。"""
    response = client.post('/api/v1/workspaces/tasks/items/batch', json={'workspace_path': str(WORKSPACE_ROOT), 'items': []})

    assert response.status_code == 401
    assert response.json() == {'detail': 'missing bearer token'}


def test_workspace_batch_create_forbids_member_role(client: TestClient) -> None:
    """普通成员不能批量创建工作区任务。"""
    response = client.post(
        '/api/v1/workspaces/tasks/items/batch',
        headers=_auth_headers('member', 2),
        json={'workspace_path': str(WORKSPACE_ROOT), 'items': [TaskItemCreate(task_key='task-001', title='示例任务一', description='中文描述一', assignee='张三').model_dump()]},
    )

    assert response.status_code == 403
    assert response.json() == {'detail': 'forbidden'}


def test_workspace_batch_create_leader_successfully_persists_items(client: TestClient) -> None:
    """队长提交合法载荷时会成功创建工作区任务条目。"""
    payload = {
        'workspace_path': str(WORKSPACE_ROOT),
        'items': [
            {'task_key': 'task-001', 'title': '示例任务一', 'status': 'todo', 'description': '中文描述一', 'assignee': '张三', 'priority': 1},
            {'task_key': 'task-002', 'title': '示例任务二', 'status': 'running', 'description': '中文描述二', 'assignee': '李四', 'priority': 2},
        ],
    }

    response = client.post('/api/v1/workspaces/tasks/items/batch', headers=_auth_headers('leader', 3), json=payload)

    assert response.status_code == 201
    assert response.json()['data']['count'] == 2
    assert {item['task_key'] for item in response.json()['data']['items']} == {'task-001', 'task-002'}
