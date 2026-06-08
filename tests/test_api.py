from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app


def _client(tmp_path: Path) -> TestClient:
    """Create a test client backed by a temporary database.

    Args:
        tmp_path: Temporary directory provided by pytest.

    Returns:
        FastAPI test client.
    """
    db_path = tmp_path / 'api.db'
    database.init_db(db_path)
    return TestClient(app, raise_server_exceptions=False)


def _register_member(client: TestClient, *, name: str, phone: str) -> dict[str, object]:
    """Register a member and return the response payload.

    Args:
        client: Test HTTP client.
        name: Member name.
        phone: Member phone.

    Returns:
        JSON response payload.
    """
    response = client.post(
        '/api/v1/auth/register',
        json={'name': name, 'phone': phone, 'password': 'secret123', 'role': 'member'},
    )
    assert response.status_code == 201
    login = client.post('/api/v1/auth/login', json={'phone': phone, 'password': 'secret123'})
    assert login.status_code == 200
    return {
        'member': response.json()['data']['member'],
        'access_token': login.json()['data']['access_token'],
    }


def _auth_header(token: str) -> dict[str, str]:
    """Build a bearer auth header.

    Args:
        token: Access token.

    Returns:
        Authorization header mapping.
    """
    return {'Authorization': f'Bearer {token}'}


def test_activities_list_supports_only_unended_filter_without_breaking_default_behavior(tmp_path: Path) -> None:
    """活动列表应支持仅返回未结束活动，并保持默认行为不变。"""
    client = _client(tmp_path)
    token = _register_member(client, name='活动用户', phone='13800000011')['access_token']

    response = client.get('/api/v1/activities', headers=_auth_header(str(token)))
    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert isinstance(payload['data'], list)

    filtered = client.get('/api/v1/activities?only_unended=true', headers=_auth_header(str(token)))
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload['message'] == '成功'
    assert isinstance(filtered_payload['data'], list)
    assert all('ended' not in item or item.get('ended') is False for item in filtered_payload['data'])


def test_activities_list_rejects_invalid_only_unended_value_with_structured_error(tmp_path: Path) -> None:
    """非法筛选参数应返回结构化错误。"""
    client = _client(tmp_path)
    token = _register_member(client, name='活动错误用户', phone='13800000012')['access_token']

    response = client.get('/api/v1/activities?only_unended=maybe', headers=_auth_header(str(token)))
    assert response.status_code == 422
    assert response.status_code == 422
    detail = response.json().get('detail', '')
    assert isinstance(detail, str)
