from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app


def _client(tmp_path: Path) -> TestClient:
    """Create a test client with an isolated database.

    Args:
        tmp_path: Temporary directory from pytest.

    Returns:
        FastAPI test client.
    """
    db_path = tmp_path / 'test.db'
    database.init_db(db_path)
    return TestClient(app, raise_server_exceptions=False)


def _auth_header(token: str) -> dict[str, str]:
    """Build an authorization header.

    Args:
        token: Bearer token string.

    Returns:
        Authorization header mapping.
    """
    return {'Authorization': f'Bearer {token}'}


def _register_member(client: TestClient, *, name: str, phone: str, role: str = 'member') -> dict[str, object]:
    """Register a member through the auth API.

    Args:
        client: FastAPI test client.
        name: Member name.
        phone: Phone number.
        role: Desired role.

    Returns:
        Response data payload.
    """
    resp = client.post(
        '/api/v1/auth/register',
        json={'name': name, 'phone': phone, 'password': 'secret123', 'role': role},
    )
    assert resp.status_code == 201
    return resp.json()['data']


def test_create_task_item_requires_chinese_title_and_description(tmp_path: Path) -> None:
    """Task item creation should reject English title and description.

    Args:
        tmp_path: Temporary directory from pytest.

    Returns:
        None.
    """
    client = _client(tmp_path)
    admin = _register_member(client, name='Admin', phone='13800001000', role='admin')
    headers = _auth_header(admin['access_token'])

    response = client.post(
        '/api/v1/workspaces/tasks/items',
        json={
            'task_key': 'task-en-title',
            'title': 'English Title',
            'status': 'todo',
            'description': '中文描述',
            'assignee': 'Admin',
            'priority': 1,
        },
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json() == {'detail': '请求参数校验失败'}

    response = client.post(
        '/api/v1/workspaces/tasks/items',
        json={
            'task_key': 'task-en-description',
            'title': '中文标题',
            'status': 'todo',
            'description': 'English description',
            'assignee': 'Admin',
            'priority': 1,
        },
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json() == {'detail': '请求参数校验失败'}


def test_create_task_item_rejects_blank_assignee(tmp_path: Path) -> None:
    """Task item creation should reject blank assignees with Chinese errors.

    Args:
        tmp_path: Temporary directory from pytest.

    Returns:
        None.
    """
    client = _client(tmp_path)
    admin = _register_member(client, name='Admin', phone='13800001001', role='admin')
    headers = _auth_header(admin['access_token'])

    response = client.post(
        '/api/v1/workspaces/tasks/items',
        json={
            'task_key': 'task-no-assignee',
            'title': '中文标题',
            'status': 'todo',
            'description': '中文描述',
            'assignee': '   ',
            'priority': 1,
        },
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json() == {'detail': '请求参数校验失败'}
