from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import ensure_workspace_tasks_table

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def _client(tmp_path: Path) -> TestClient:
    """Create a test client with an isolated database.

    Args:
        tmp_path: Temporary directory from pytest.

    Returns:
        FastAPI test client.
    """
    db_path = tmp_path / 'comments.db'
    database.init_db(db_path)
    ensure_workspace_tasks_table()
    return TestClient(app, raise_server_exceptions=False)


def _auth_header(token: str) -> dict[str, str]:
    """Build an authorization header.

    Args:
        token: Bearer token.

    Returns:
        Authorization header dictionary.
    """
    return {'Authorization': f'Bearer {token}'}


def _admin_headers(client: TestClient) -> dict[str, str]:
    """Create an admin token for privileged API calls.

    Args:
        client: FastAPI test client.

    Returns:
        Authorization header dictionary.
    """
    response = client.post(
        '/api/v1/auth/register',
        json={'name': 'Admin', 'phone': '13800000999', 'password': 'secret123', 'role': 'admin'},
    )
    assert response.status_code == 201
    return _auth_header(response.json()['data']['access_token'])


def _create_workspace_task(client: TestClient, headers: dict[str, str], task_key: str = 'auto-summary-task') -> None:
    """Seed one workspace task for comment tests.

    Args:
        client: FastAPI test client.
        headers: Authorization headers.
        task_key: Unique task key.

    Returns:
        None.
    """
    response = client.post(
        '/api/v1/workspaces/tasks/items',
        json={
            'task_key': task_key,
            'title': '自动摘要任务',
            'status': 'todo',
            'description': '用于验证摘要评论生成',
            'priority': 1,
            'workspace_path': str(WORKSPACE_ROOT),
        },
        headers=headers,
    )
    assert response.status_code == 201


def test_auto_summary_comments_endpoint_returns_three_chinese_summaries(tmp_path: Path) -> None:
    """Auto summary endpoint should return three Chinese summaries and persist them.

    Args:
        tmp_path: Temporary directory from pytest.

    Returns:
        None.
    """
    client = _client(tmp_path)
    headers = _admin_headers(client)
    _create_workspace_task(client, headers)

    response = client.post(
        '/api/v1/workspaces/summary',
        json={
            'workspace_path': str(WORKSPACE_ROOT),
            'content': '请根据这段内容生成三条中文摘要并保存到评论中。',
            'task_key': 'auto-summary-task',
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['task_key'] == 'auto-summary-task'
    assert len(payload['data']['summaries']) == 3
    assert all(isinstance(item, str) and item for item in payload['data']['summaries'])

    comments_response = client.get(
        '/api/v1/workspaces/tasks/comments',
        params={'workspace_path': str(WORKSPACE_ROOT), 'task_key': 'auto-summary-task'},
        headers=headers,
    )
    assert comments_response.status_code == 200
    comments = comments_response.json()['data']['comments']
    assert len(comments) == 3
    assert all(comment['comment_type'] == 'summary' for comment in comments)
    assert all('摘要' in comment['content'] for comment in comments)


def test_auto_summary_comments_endpoint_rejects_invalid_payload(tmp_path: Path) -> None:
    """Auto summary endpoint should validate request payloads.

    Args:
        tmp_path: Temporary directory from pytest.

    Returns:
        None.
    """
    client = _client(tmp_path)
    headers = _admin_headers(client)

    response = client.post(
        '/api/v1/workspaces/summary',
        json={'workspace_path': str(WORKSPACE_ROOT), 'content': ''},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json() == {'detail': '请求参数校验失败'}
