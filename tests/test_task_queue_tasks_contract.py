from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import upsert_workspace_task_item

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def _client(tmp_path: Path) -> TestClient:
    """创建隔离数据库的测试客户端。

    Args:
        tmp_path: pytest 临时目录。

    Returns:
        FastAPI 测试客户端。
    """
    database.init_db(tmp_path / 'task_queue_tasks.db')
    return TestClient(app, raise_server_exceptions=False)


def _leader_headers(client: TestClient) -> dict[str, str]:
    """创建 leader 鉴权头。

    Args:
        client: FastAPI 测试客户端。

    Returns:
        Authorization 请求头。
    """
    phone = f'15550004100-{id(client)}'
    response = client.post('/api/v1/auth/register', json={'name': 'Leader', 'phone': phone, 'password': 'secret123', 'role': 'member'})
    assert response.status_code == 201
    member_id = response.json()['data']['member']['id']
    with database.connect() as connection:
        connection.execute('UPDATE members SET role = ? WHERE id = ?', ('leader', member_id))
    token = client.post('/api/v1/auth/login', json={'phone': phone, 'password': 'secret123'}).json()['data']['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_task_queue_tasks_returns_frontend_contract(tmp_path: Path) -> None:
    """任务队列列表接口应返回前端需要的任务契约字段。

    Args:
        tmp_path: pytest 临时目录。
    """
    client = _client(tmp_path)
    headers = _leader_headers(client)
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='task-queue-contract',
        title='修复任务列表契约',
        status='running',
        assignee='backend-dev',
        priority=8,
        metadata={'description': '补齐 /api/v1/workspaces/task-queue/tasks'},
    )

    response = client.get('/api/v1/workspaces/task-queue/tasks', params={'workspace': f'workspace:{WORKSPACE_ROOT}', 'limit': 10}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '成功'
    assert body['data'][0] == {
        'id': 'task-queue-contract',
        'title': '修复任务列表契约',
        'assignee': 'backend-dev',
        'status': 'running',
        'priority': 8,
        'workspace': str(WORKSPACE_ROOT.resolve()),
        'created_at': body['data'][0]['created_at'],
        'updated_at': body['data'][0]['updated_at'],
    }
    assert body['data'][0]['created_at']
    assert body['data'][0]['updated_at']



def test_task_queue_tasks_rejects_invalid_status(tmp_path: Path) -> None:
    """任务队列列表接口应结构化返回非法状态错误。

    Args:
        tmp_path: pytest 临时目录。
    """
    client = _client(tmp_path)
    headers = _leader_headers(client)

    response = client.get('/api/v1/workspaces/task-queue/tasks', params={'status': 'unknown'}, headers=headers)

    assert response.status_code == 422
    assert response.json() == {'detail': '任务状态筛选参数不合法'}
