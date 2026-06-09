from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import database as db
from backend.app import app
from backend.database import init_db
from backend.models import TaskItemCreate
from backend.routes.common import CurrentUser, token_for_member


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """创建隔离的数据库客户端。"""
    db_path = tmp_path / 'workspaces.db'
    db.DB_PATH = db_path
    init_db(db_path)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _auth_headers(role: str, member_id: int) -> dict[str, str]:
    """为指定角色生成认证头。"""
    token = token_for_member(CurrentUser(id=member_id, role=role, member=None))
    return {'Authorization': f'Bearer {token}'}


def test_读取工作区任务_管理员携带合法路径_返回200(client: TestClient) -> None:
    """管理员读取工作区任务时返回 200。"""
    response = client.get('/api/v1/workspaces/tasks?workspace_path=/root/autodl-tmp/projects/hermes-swarm-lab&limit=1', headers=_auth_headers('admin', 1))
    assert response.status_code == 200
    assert response.json()['message'] == '成功'


def test_读取工作区任务_未携带认证信息_返回401(client: TestClient) -> None:
    """未登录时不能读取工作区任务。"""
    response = client.get('/api/v1/workspaces/tasks?workspace_path=/root/autodl-tmp/projects/hermes-swarm-lab')
    assert response.status_code == 401
    assert response.json()['detail'] == 'missing bearer token'


def test_读取工作区任务_普通成员访问_返回403(client: TestClient) -> None:
    """普通成员无权读取工作区任务。"""
    response = client.get('/api/v1/workspaces/tasks?workspace_path=/root/autodl-tmp/projects/hermes-swarm-lab', headers=_auth_headers('member', 2))
    assert response.status_code == 403
    assert response.json()['detail'] == 'forbidden'


def test_读取工作区任务_非法选择器_返回422(client: TestClient) -> None:
    """非法 workspace 选择器会被拒绝。"""
    response = client.get('/api/v1/workspaces/tasks?workspace=invalid-selector', headers=_auth_headers('leader', 3))
    assert response.status_code == 422
    assert response.json()['detail'] == '工作区选择器不合法'


def test_读取工作区摘要_合法路径_返回200(client: TestClient) -> None:
    """队长读取工作区摘要时返回 200。"""
    response = client.get('/api/v1/workspaces/summary?workspace_path=/root/autodl-tmp/projects/hermes-swarm-lab', headers=_auth_headers('leader', 4))
    assert response.status_code == 200
    assert response.json()['data']['workspace_path'].endswith('hermes-swarm-lab')


def test_读取工作区摘要_缺少必填参数_返回422(client: TestClient) -> None:
    """缺少 workspace_path 时会触发参数校验错误。"""
    response = client.get('/api/v1/workspaces/summary', headers=_auth_headers('leader', 5))
    assert response.status_code == 422


def test_批量创建工作区任务_空列表_返回422(client: TestClient) -> None:
    """批量创建时空任务列表会被拒绝。"""
    payload = {'workspace_path': '/root/autodl-tmp/projects/hermes-swarm-lab', 'items': []}
    response = client.post('/api/v1/workspaces/tasks/items/batch', headers=_auth_headers('leader', 6), json=payload)
    assert response.status_code == 422
    assert response.json()['detail'] == '任务列表不能为空'


def test_批量创建工作区任务_合法载荷_返回201(client: TestClient) -> None:
    """队长提交合法载荷时可批量创建工作区任务。"""
    payload = {
        'workspace_path': '/root/autodl-tmp/projects/hermes-swarm-lab',
        'items': [TaskItemCreate(task_key='task-001', title='示例任务一', description='中文描述一', assignee='张三').model_dump()],
    }
    response = client.post('/api/v1/workspaces/tasks/items/batch', headers=_auth_headers('leader', 7), json=payload)
    assert response.status_code == 201
    assert response.json()['data']['count'] == 1
