from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app
from conftest import make_auth_headers

client = TestClient(app)
AUTH_HEADERS = None  # Replaced by make_auth_headers(client, ...) at call site
WORKSPACE_PATH = '/root/autodl-tmp/projects/hermes-swarm-lab'


def _ensure_worker(worker_key: str) -> None:
    """Ensure an assignee exists for import validation.

    Args:
        worker_key: Worker identifier used by imported tasks.
    """
    response = client.post(
        '/api/v1/workers/intake',
        json={'worker_key': worker_key, 'name': worker_key, 'status': 'active', 'capabilities': ['backend']},
        headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
    )
    assert response.status_code == 201


def test_import_task_items_success_persists_workspace_items() -> None:
    """Import task metadata and persist workspace task items."""
    _ensure_worker('alice')
    _ensure_worker('bob')
    response = client.post(
        '/api/v1/workspaces/tasks/items/import',
        json={
            'workspace_path': WORKSPACE_PATH,
            'items': [
                {
                    'task_key': 'creative-001',
                    'title': '创建中文创意任务A',
                    'description': '导入后应可在任务面板中查询到',
                    'status': 'todo',
                    'assignee': 'alice',
                    'priority': 3,
                },
                {
                    'task_key': 'creative-002',
                    'title': '创建中文创意任务B',
                    'description': '同一批导入的第二条记录',
                    'status': 'doing',
                    'assignee': 'bob',
                    'priority': 1,
                },
            ]
        },
        headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
    )
    assert response.status_code == 201
    body = response.json()
    assert body['message'] == '成功'
    assert body['data']['count'] == 2
    assert body['data']['items'][0]['task_key'] == 'creative-001'
    assert body['data']['items'][0]['title'] == '创建中文创意任务A'
    assert body['data']['items'][0]['status'] == 'todo'
    assert body['data']['items'][0]['description'] == '导入后应可在任务面板中查询到'
    assert body['data']['items'][0]['assignee'] == 'alice'
    assert body['data']['items'][0]['priority'] == 3
    assert body['data']['items'][0]['workspace_path'] == WORKSPACE_PATH
    assert body['data']['items'][0]['metadata'] == {'description': '导入后应可在任务面板中查询到'}
    assert body['data']['items'][1]['task_key'] == 'creative-002'
    assert body['data']['items'][1]['title'] == '创建中文创意任务B'
    assert body['data']['items'][1]['status'] == 'running'
    assert body['data']['items'][1]['description'] == '同一批导入的第二条记录'
    assert body['data']['items'][1]['assignee'] == 'bob'
    assert body['data']['items'][1]['priority'] == 1
    assert body['data']['items'][1]['workspace_path'] == WORKSPACE_PATH
    assert body['data']['items'][1]['metadata'] == {'description': '同一批导入的第二条记录'}

    board_response = client.get(
        '/api/v1/workspaces/tasks',
        params={'workspace_path': WORKSPACE_PATH},
        headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
    )
    assert board_response.status_code == 200
    board_body = board_response.json()
    task_keys = {item['task_key'] for item in board_body['data']}
    assert 'creative-001' in task_keys
    assert 'creative-002' in task_keys


def test_import_task_items_rejects_empty_items() -> None:
    """Reject empty batch imports with structured validation errors."""
    response = client.post(
        '/api/v1/workspaces/tasks/items/import',
        json={'items': []},
        headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
    )
    assert response.status_code == 422
    assert response.json() == {'detail': '创意任务必须正好两张'}


def test_import_task_items_rejects_missing_assignee() -> None:
    """Reject imports that reference a non-existent assignee."""
    response = client.post(
        '/api/v1/workspaces/tasks/items/import',
        json={
            'items': [
                {
                    'task_key': 'creative-003',
                    'title': '创建中文创意任务C',
                    'description': '负责人不存在时必须报错',
                    'status': 'todo',
                    'assignee': 'ghost-worker',
                    'priority': 2,
                },
                {
                    'task_key': 'creative-004',
                    'title': '创建中文创意任务D',
                    'description': '第二条用于满足两张限制',
                    'status': 'todo',
                    'assignee': 'alice',
                    'priority': 1,
                },
            ]
        },
        headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
    )
    assert response.status_code == 422
    assert response.json() == {'detail': '负责人不存在'}


def test_import_task_items_rejects_blocked_status() -> None:
    """Reject blocked status during task import with a Chinese error message."""
    response = client.post(
        '/api/v1/workspaces/tasks/items/import',
        json={
            'items': [
                {
                    'task_key': 'creative-005',
                    'title': '创建中文创意任务E',
                    'description': 'blocked 状态必须拒绝',
                    'status': 'blocked',
                    'assignee': 'alice',
                    'priority': 1,
                },
                {
                    'task_key': 'creative-006',
                    'title': '创建中文创意任务F',
                    'description': '第二条用于满足两张限制',
                    'status': 'todo',
                    'assignee': 'bob',
                    'priority': 1,
                },
            ]
        },
        headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
    )
    assert response.status_code == 422
    assert response.json() == {'detail': '任务状态不合法'}


def test_import_task_items_uses_workspace_query_when_item_missing_path() -> None:
    """Use the workspace query parameter as fallback workspace path."""
    _ensure_worker('carol')
    _ensure_worker('dave')
    response = client.post(
        '/api/v1/workspaces/tasks/items/import',
        params={'workspace_path': WORKSPACE_PATH},
        json={
            'items': [
                {
                    'task_key': 'creative-007',
                    'title': '创建中文创意任务G',
                    'description': '未显式传 workspace_path 时使用查询参数',
                    'status': 'todo',
                    'assignee': 'carol',
                    'priority': 4,
                },
                {
                    'task_key': 'creative-008',
                    'title': '创建中文创意任务H',
                    'description': '第二条同样继承查询参数',
                    'status': 'doing',
                    'assignee': 'dave',
                    'priority': 2,
                },
            ]
        },
        headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
    )
    assert response.status_code == 201
    body = response.json()
    assert body['data']['count'] == 2
    assert body['data']['items'][0]['workspace_path'] == WORKSPACE_PATH
    assert body['data']['items'][1]['workspace_path'] == WORKSPACE_PATH
