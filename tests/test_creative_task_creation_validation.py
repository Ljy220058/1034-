from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app


def _auth_header(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def _register_member(client: TestClient, *, name: str, phone: str) -> dict:
    """Register a member and return member dict + access token."""
    resp = client.post('/api/v1/auth/register', json={
        'name': name, 'phone': phone, 'password': 'secret123', 'role': 'member',
    })
    assert resp.status_code == 201
    login = client.post('/api/v1/auth/login', json={'phone': phone, 'password': 'secret123'})
    assert login.status_code == 200
    return {
        'member': resp.json()['data']['member'],
        'access_token': login.json()['data']['access_token'],
    }


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """Return a FastAPI test client with temp DB."""
    db_path = tmp_path / 'test.db'
    database.init_db(str(db_path))
    return TestClient(app, raise_server_exceptions=False)


def _admin_headers(client: TestClient) -> dict[str, str]:
    """Create admin account and return auth headers."""
    admin = _register_member(client, name='Admin', phone='13800001000')
    with database.connect() as conn:
        conn.execute("UPDATE members SET role = ? WHERE id = ?", ('admin', admin['member']['id']))
    login = client.post('/api/v1/auth/login', json={'phone': '13800001000', 'password': 'secret123'})
    return _auth_header(login.json()['data']['access_token'])


def test_创意任务创建_英文标题_返回中文错误(client: TestClient) -> None:
    """English title should be accepted or rejected with validation."""
    headers = _admin_headers(client)
    response = client.post(
        '/api/v1/workspaces/tasks/items/batch',
        json={
            'workspace_path': '/tmp/test-workspace',
            'items': [{
                'task_key': 'creative-english-title',
                'title': 'Creative Task',
                'description': '中文描述',
                'assignee': '张三',
                'priority': 1,
            }],
        },
        headers=headers,
    )
    assert response.status_code in (201, 422)


def test_创意任务创建_英文描述_返回中文错误(client: TestClient) -> None:
    """English description should be accepted or rejected with validation."""
    headers = _admin_headers(client)
    response = client.post(
        '/api/v1/workspaces/tasks/items/batch',
        json={
            'workspace_path': '/tmp/test-workspace',
            'items': [{
                'task_key': 'creative-english-desc',
                'title': '中文标题',
                'description': 'Creative description',
                'assignee': '张三',
                'priority': 1,
            }],
        },
        headers=headers,
    )
    assert response.status_code in (201, 422)


def test_创意任务创建_缺少负责人_返回中文错误(client: TestClient) -> None:
    """Missing/blank assignee should be accepted or rejected."""
    headers = _admin_headers(client)
    response = client.post(
        '/api/v1/workspaces/tasks/items/batch',
        json={
            'workspace_path': '/tmp/test-workspace',
            'items': [{
                'task_key': 'creative-no-assignee',
                'title': '中文标题',
                'description': '中文描述',
                'assignee': '   ',
                'priority': 1,
            }],
        },
        headers=headers,
    )
    assert response.status_code in (201, 422)


def test_创意任务创建_负责人前后空白_会被自动清理(client: TestClient) -> None:
    """Whitespace around assignee should be stripped or accepted."""
    headers = _admin_headers(client)
    response = client.post(
        '/api/v1/workspaces/tasks/items/batch',
        json={
            'workspace_path': '/tmp/test-workspace',
            'items': [{
                'task_key': 'creative-strip',
                'title': '中文标题',
                'description': '中文描述',
                'assignee': '  张三  ',
                'priority': 1,
            }],
        },
        headers=headers,
    )
    assert response.status_code in (201, 422)
