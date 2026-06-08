from __future__ import annotations

import os

from fastapi.testclient import TestClient

os.environ.setdefault('RUNNING_CLUB_JWT_SECRET', 'pytest-running-club-secret-with-at-least-32-bytes')

from backend.app import app  # noqa: E402
from backend.database import connect  # noqa: E402

client = TestClient(app)


def _make_token(role: str = 'member', phone: str = '17700000001') -> str:
    """注册并登录测试用户，返回 JWT token。

    Args:
        role: 目标角色。
        phone: 用户手机号。

    Returns:
        Bearer token 字符串。
    """
    with connect() as connection:
        existing = connection.execute('SELECT id FROM members WHERE phone = ?', (phone,)).fetchone()
    if existing is None:
        register = client.post(
            '/api/v1/auth/register',
            json={'name': '测试用户', 'phone': phone, 'password': 'secret123', 'role': 'member'},
        )
        assert register.status_code == 201, register.text
    if role != 'member':
        with connect() as connection:
            connection.execute('UPDATE members SET role = ? WHERE phone = ?', (role, phone))
    login = client.post('/api/v1/auth/login', json={'phone': phone, 'password': 'secret123'})
    assert login.status_code == 200, login.text
    return login.json()['data']['access_token']


def test_batch_route_requires_login() -> None:
    """未登录访问批量路由应返回 401。"""
    response = client.post('/api/v1/creative-cards/batch-route', json={'items': [{'description': '后端接口优化'}]})
    assert response.status_code == 401
    assert response.json() == {'detail': 'missing bearer token'}


def test_batch_route_forbids_member() -> None:
    """普通 member 访问批量路由应返回 403。"""
    token = _make_token(role='member', phone='17700000002')
    response = client.post(
        '/api/v1/creative-cards/batch-route',
        headers={'Authorization': f'Bearer {token}'},
        json={'items': [{'description': '后端接口优化'}]},
    )
    assert response.status_code == 403
    assert response.json() == {'detail': 'forbidden'}


def test_batch_route_accepts_admin_and_routes_items() -> None:
    """管理员访问批量路由应成功并返回 ApiResponse。"""
    token = _make_token(role='admin', phone='17700000003')
    payload = {
        'items': [
            {'description': '后端接口优化', 'task_type': '接口整理'},
            {'description': '文档补充与README更新'},
            {'description': '后端接口优化'},
        ]
    }
    response = client.post(
        '/api/v1/creative-cards/batch-route',
        headers={'Authorization': f'Bearer {token}'},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '成功'
    assert body['data']['summary'] == {'total': 3, 'created': 2, 'failed': 0, 'duplicates': 1}
    assert body['data']['results'][0]['status'] == 'created'
    assert body['data']['results'][1]['worker'] == 'docs-writer'
    assert body['data']['results'][2]['status'] == 'duplicate'
