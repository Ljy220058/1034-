from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import upsert_workspace_task_item
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
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


def test_workspace_summary_returns_structured_counts(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Workspace summary should expose task, worker, and duplicate counts.

    Args:
        client: FastAPI test client.
        monkeypatch: Pytest environment patch helper.
    """
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))
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
        status='running',
        description='后端负责创建和分流任务卡片',
        assignee='后端工人',
        priority=8,
        metadata={'lane': 'backend'},
    )
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='task-backend-copy',
        title='实现后端任务分流',
        status='blocked',
        description='重复标题用于检测',
        assignee=None,
        priority=7,
        metadata={'lane': 'backend'},
    )

    response = client.get(
        '/api/v1/workspaces/summary',
        params={'workspace_path': str(WORKSPACE_ROOT)},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '成功'
    assert body['data']['workspace_path'] == str(WORKSPACE_ROOT.resolve())
    assert body['data']['workers']['total'] >= 1
    assert body['data']['tasks']['total'] >= 2
    assert body['data']['duplicates']['count'] == 1
    assert body['data']['duplicates']['items'][0]['count'] == 2


def test_workspace_tasks_endpoint_supports_status_filter(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Workspace tasks endpoint should filter by status.

    Args:
        client: FastAPI test client.
        monkeypatch: Pytest environment patch helper.
    """
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))
    headers = _leader_headers(client)
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='task-todo',
        title='待办任务',
        status='todo',
        description='待处理',
        assignee=None,
        priority=5,
        metadata={},
    )
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='task-running',
        title='运行中任务',
        status='running',
        description='处理中',
        assignee='后端工人',
        priority=9,
        metadata={},
    )

    response = client.get(
        '/api/v1/workspaces/tasks',
        params={'workspace_path': str(WORKSPACE_ROOT), 'status': 'running', 'limit': 10},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['workspace_path'] == str(WORKSPACE_ROOT.resolve())
    assert len(payload['data']['items']) == 1
    assert payload['data']['items'][0]['status'] == 'running'


def test_workspace_endpoints_forbid_member_access(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Workspace endpoints should reject ordinary members.

    Args:
        client: FastAPI test client.
        monkeypatch: Pytest environment patch helper.
    """
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))
    member = client.post(
        '/api/v1/auth/register',
        json={'name': 'Member', 'phone': f'15550003099-{id(client)}', 'password': 'secret123', 'role': 'member'},
    )
    assert member.status_code == 201
    token = client.post(
        '/api/v1/auth/login',
        json={'phone': f'15550003099-{id(client)}', 'password': 'secret123'},
    ).json()['data']['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    responses = [
        client.get('/api/v1/workspaces/tasks', params={'workspace_path': str(WORKSPACE_ROOT)}, headers=headers),
        client.get('/api/v1/workspaces/tasks/items', params={'workspace_path': str(WORKSPACE_ROOT)}, headers=headers),
        client.get('/api/v1/workers/board', params={'workspace_path': str(WORKSPACE_ROOT)}, headers=headers),
        client.get('/api/v1/workers/summary', headers=headers),
        client.get('/api/v1/workers/recommendations', params={'workspace_path': str(WORKSPACE_ROOT)}, headers=headers),
    ]

    for response in responses:
        assert response.status_code == 403
        assert response.json() == {'detail': 'forbidden'}


def test_workspace_task_import_persists_board_items(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Task import should persist validated tasks into workspace_tasks.

    Args:
        client: FastAPI test client.
        monkeypatch: Pytest environment patch helper.
    """
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))
    headers = _leader_headers(client)
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='import-worker',
        title='导入负责人',
        status='running',
        description='负责导入相关任务',
        assignee='后端工人',
        priority=10,
        metadata={},
    )

    result = batch_import_task_metadata(
        [
            {
                'task_key': 'import-001',
                'title': '导入后落库',
                'description': '验证导入后能被任务板查询到',
                'status': 'doing',
                'assignee': '后端工人',
                'priority': 9,
                'workspace_path': str(WORKSPACE_ROOT),
            }
        ]
    )

    assert result.count == 1
    assert result.items[0].metadata == {
        'description': '验证导入后能被任务板查询到',
        'workspace_path': str(WORKSPACE_ROOT),
    }

    response = client.get(
        '/api/v1/workspaces/tasks',
        params={'workspace_path': str(WORKSPACE_ROOT), 'status': 'running', 'limit': 20},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    task_keys = [item['task_key'] for item in payload['data']]
    assert 'import-001' in task_keys



def test_workspace_batch_create_rejects_unauthenticated_requests(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Batch creation should require authentication."""
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))

    response = client.post(
        '/api/v1/workspaces/tasks/items/batch',
        json={
            'workspace_path': str(WORKSPACE_ROOT),
            'items': [
                {
                    'task_key': 'task-001',
                    'title': '示例任务一',
                    'status': 'todo',
                    'description': '描述一',
                    'assignee': '张三',
                    'priority': 1,
                },
                {
                    'task_key': 'task-002',
                    'title': '示例任务二',
                    'status': 'todo',
                    'description': '描述二',
                    'assignee': '李四',
                    'priority': 2,
                },
            ],
        },
    )

    assert response.status_code == 401
    assert response.json() == {'detail': 'missing bearer token'}



def test_workspace_batch_create_forbids_member_access(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Batch creation should reject ordinary members."""
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))
    member = client.post(
        '/api/v1/auth/register',
        json={'name': 'Member', 'phone': f'15550003101-{id(client)}', 'password': 'secret123', 'role': 'member'},
    )
    assert member.status_code == 201
    token = client.post(
        '/api/v1/auth/login',
        json={'phone': f'15550003101-{id(client)}', 'password': 'secret123'},
    ).json()['data']['access_token']

    response = client.post(
        '/api/v1/workspaces/tasks/items/batch',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'workspace_path': str(WORKSPACE_ROOT),
            'items': [
                {
                    'task_key': 'task-001',
                    'title': '示例任务一',
                    'status': 'todo',
                    'description': '描述一',
                    'assignee': '张三',
                    'priority': 1,
                },
                {
                    'task_key': 'task-002',
                    'title': '示例任务二',
                    'status': 'todo',
                    'description': '描述二',
                    'assignee': '李四',
                    'priority': 2,
                },
            ],
        },
    )

    assert response.status_code == 403
    assert response.json() == {'detail': 'forbidden'}



def test_workspace_batch_create_allows_leader_and_admin(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Batch creation should allow leader and admin users."""
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))
    leader_headers = _leader_headers(client)

    leader_response = client.post(
        '/api/v1/workspaces/tasks/items/batch',
        headers=leader_headers,
        json={
            'workspace_path': str(WORKSPACE_ROOT),
            'items': [
                {
                    'task_key': 'leader-task-001',
                    'title': '领导创建任务一',
                    'status': 'todo',
                    'description': '领导创建描述一',
                    'assignee': '张三',
                    'priority': 1,
                },
                {
                    'task_key': 'leader-task-002',
                    'title': '领导创建任务二',
                    'status': 'todo',
                    'description': '领导创建描述二',
                    'assignee': '李四',
                    'priority': 2,
                },
            ],
        },
    )

    assert leader_response.status_code == 201
    leader_body = leader_response.json()
    assert leader_body['message'] == '批量创建成功'
    assert leader_body['data']['count'] == 2
    assert len(leader_body['data']['items']) == 2

    admin = client.post(
        '/api/v1/auth/register',
        json={'name': 'Admin', 'phone': f'15550003102-{id(client)}', 'password': 'secret123', 'role': 'member'},
    )
    assert admin.status_code == 201
    admin_id = admin.json()['data']['member']['id']
    from backend.database import connect
    with connect() as connection:
        connection.execute('UPDATE members SET role = ? WHERE id = ?', ('admin', admin_id))
    admin_token = client.post(
        '/api/v1/auth/login',
        json={'phone': f'15550003102-{id(client)}', 'password': 'secret123'},
    ).json()['data']['access_token']

    admin_response = client.post(
        '/api/v1/workspaces/tasks/items/batch',
        headers={'Authorization': f'Bearer {admin_token}'},
        json={
            'workspace_path': str(WORKSPACE_ROOT),
            'items': [
                {
                    'task_key': 'admin-task-001',
                    'title': '管理员创建任务一',
                    'status': 'todo',
                    'description': '管理员创建描述一',
                    'assignee': '王五',
                    'priority': 3,
                },
                {
                    'task_key': 'admin-task-002',
                    'title': '管理员创建任务二',
                    'status': 'todo',
                    'description': '管理员创建描述二',
                    'assignee': '赵六',
                    'priority': 4,
                },
            ],
        },
    )

    assert admin_response.status_code == 201
    admin_body = admin_response.json()
    assert admin_body['message'] == '批量创建成功'
    assert admin_body['data']['count'] == 2
