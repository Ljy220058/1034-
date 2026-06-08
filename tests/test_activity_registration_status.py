from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from tests.test_api import _auth_header, _register_member


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """创建使用临时 SQLite 数据库的测试客户端。

    Args:
        tmp_path: pytest 临时目录。

    Returns:
        FastAPI 测试客户端。
    """
    database.init_db(tmp_path / 'activity-registration-status.db')
    return TestClient(app, raise_server_exceptions=False)


def _leader_headers(client: TestClient) -> dict[str, str]:
    """创建领队并返回请求头。

    Args:
        client: FastAPI 测试客户端。

    Returns:
        领队登录请求头。
    """
    leader = _register_member(client, name='状态领队', phone='16670000001')
    with database.connect() as connection:
        connection.execute('UPDATE members SET role = ? WHERE id = ?', ('leader', leader['member']['id']))
    login = client.post('/api/v1/auth/login', json={'phone': '16670000001', 'password': 'secret123'})
    return _auth_header(str(login.json()['data']['access_token']))


def _create_activity(client: TestClient, headers: dict[str, str], title: str) -> dict[str, object]:
    """创建活动并返回活动数据。

    Args:
        client: FastAPI 测试客户端。
        headers: 领队请求头。
        title: 活动标题。

    Returns:
        活动响应数据。
    """
    response = client.post(
        '/api/v1/activities',
        json={'title': title, 'start_time': '2026-06-08T07:00:00+00:00', 'location': '公园'},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()['data']


def test_活动列表_返回当前成员每个活动报名状态(client: TestClient) -> None:
    """活动列表应补充当前登录成员对每个活动的报名状态。"""
    leader_headers = _leader_headers(client)
    member = _register_member(client, name='报名状态成员', phone='16670000002')
    joined = _create_activity(client, leader_headers, '已报名活动')
    unjoined = _create_activity(client, leader_headers, '未报名活动')
    signup = client.post(
        f"/api/v1/activities/{joined['id']}/registrations",
        json={'member_id': member['member']['id']},
        headers=_auth_header(str(member['access_token'])),
    )
    assert signup.status_code == 201

    response = client.get('/api/v1/activities', headers=_auth_header(str(member['access_token'])))

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    by_id = {item['id']: item for item in payload['data']}
    assert by_id[joined['id']]['registration_status'] == 'registered'
    assert by_id[joined['id']]['is_registered'] is True
    assert by_id[unjoined['id']]['registration_status'] == 'not_registered'
    assert by_id[unjoined['id']]['is_registered'] is False


def test_活动详情_返回当前成员报名状态(client: TestClient) -> None:
    """活动详情应返回当前登录成员的报名状态。"""
    leader_headers = _leader_headers(client)
    member = _register_member(client, name='详情状态成员', phone='16670000003')
    activity = _create_activity(client, leader_headers, '详情报名状态活动')
    signup = client.post(
        f"/api/v1/activities/{activity['id']}/registrations",
        json={'member_id': member['member']['id']},
        headers=_auth_header(str(member['access_token'])),
    )
    assert signup.status_code == 201

    response = client.get(f"/api/v1/activities/{activity['id']}", headers=_auth_header(str(member['access_token'])))

    assert response.status_code == 200
    data = response.json()['data']
    assert data['registration_status'] == 'registered'
    assert data['is_registered'] is True


def test_活动列表和详情_未登录时返回明确默认报名状态(client: TestClient) -> None:
    """未登录访问活动列表和详情时应返回未报名默认值。"""
    leader_headers = _leader_headers(client)
    activity = _create_activity(client, leader_headers, '未登录默认状态活动')

    list_response = client.get('/api/v1/activities')
    detail_response = client.get(f"/api/v1/activities/{activity['id']}")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    list_item = list_response.json()['data'][0]
    detail_item = detail_response.json()['data']
    assert list_item['registration_status'] == 'not_registered'
    assert list_item['is_registered'] is False
    assert detail_item['registration_status'] == 'not_registered'
    assert detail_item['is_registered'] is False
