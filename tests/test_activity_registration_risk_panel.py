from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from tests.test_api import _auth_header, _register_member


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    database.init_db(tmp_path / 'activity-registration-risk.db')
    return TestClient(app, raise_server_exceptions=False)


def _leader_headers(client: TestClient) -> dict[str, str]:
    leader = _register_member(client, name='领队', phone='16660000001')
    with database.connect() as connection:
        connection.execute('UPDATE members SET role = ? WHERE id = ?', ('leader', leader['member']['id']))
    login = client.post('/api/v1/auth/login', json={'phone': '16660000001', 'password': 'secret123'})
    return _auth_header(login.json()['data']['access_token'])


def _member(client: TestClient, suffix: str) -> dict[str, object]:
    return _register_member(client, name=f'跑友{suffix}', phone=f'166600000{suffix}')


def _activity(client: TestClient, headers: dict[str, str], *, quota: int = 2) -> dict[str, object]:
    payload = {'title': '活动报名风险冒烟', 'start_time': '2026-06-07T07:00:00+00:00', 'location': '公园', 'max_participants': quota}
    response = client.post('/api/v1/activities', json=payload, headers=headers)
    return response.json()['data']


def _signup(client: TestClient, activity_id: int, member: dict[str, object]):
    return client.post(
        f'/api/v1/activities/{activity_id}/registrations',
        json={'member_id': member['member']['id']},
        headers=_auth_header(member['access_token']),
    )


def test_正常报名_名额未满_返回201并登记为已报名(client: TestClient) -> None:
    headers = _leader_headers(client)
    member = _member(client, '002')
    activity = _activity(client, headers, quota=2)

    response = _signup(client, activity['id'], member)

    assert response.status_code == 201, '正常报名失败：请检查报名写入流程'
    assert response.json()['data']['status'] == 'registered'


def test_超出名额_活动仅剩零名额_返回409和中文失败提示(client: TestClient) -> None:
    headers = _leader_headers(client)
    activity = _activity(client, headers, quota=1)
    _signup(client, activity['id'], _member(client, '002'))

    response = _signup(client, activity['id'], _member(client, '003'))

    assert response.status_code == 409, '超额报名未拦截：请检查名额上限规则'
    assert '名额已满' in response.json()['detail']


def test_重复报名_同一成员已报名_返回409和重复提示(client: TestClient) -> None:
    headers = _leader_headers(client)
    member = _member(client, '002')
    activity = _activity(client, headers, quota=2)
    _signup(client, activity['id'], member)

    response = _signup(client, activity['id'], member)

    assert response.status_code == 409, '重复报名未拦截：请检查唯一报名规则'
    assert '已报名' in response.json()['detail']


def test_取消后重新报名_原报名已取消_返回201并恢复已报名(client: TestClient) -> None:
    headers = _leader_headers(client)
    member = _member(client, '002')
    activity = _activity(client, headers, quota=1)
    _signup(client, activity['id'], member)
    client.delete(f"/api/v1/activities/{activity['id']}/registrations/{member['member']['id']}", headers=_auth_header(member['access_token']))

    response = _signup(client, activity['id'], member)

    assert response.status_code == 201, '取消后重报失败：请检查 cancelled 状态恢复逻辑'
    assert response.json()['data']['status'] == 'registered'


def test_报名请求_缺少成员编号_返回422(client: TestClient) -> None:
    headers = _leader_headers(client)
    activity = _activity(client, headers)

    response = client.post(f"/api/v1/activities/{activity['id']}/registrations", json={}, headers=headers)

    assert response.status_code == 422
    detail = response.json()['detail']
    assert isinstance(detail, str) and ('Field required' in detail or 'member_id' in detail.lower() or '输入验证' in detail)


def test_报名请求_未认证_返回401(client: TestClient) -> None:
    headers = _leader_headers(client)
    member = _member(client, '002')
    activity = _activity(client, headers)

    response = client.post(f"/api/v1/activities/{activity['id']}/registrations", json={'member_id': member['member']['id']})

    assert response.status_code == 401
    assert 'missing bearer token' in response.json()['detail']


def test_报名请求_普通成员替他人报名_返回403(client: TestClient) -> None:
    headers = _leader_headers(client)
    member = _member(client, '002')
    other = _member(client, '003')
    activity = _activity(client, headers)

    response = client.post(f"/api/v1/activities/{activity['id']}/registrations", json={'member_id': other['member']['id']}, headers=_auth_header(member['access_token']))

    assert response.status_code == 403
    assert response.json()['detail'] == 'forbidden'


def test_风险冒烟面板_查看活动_返回四个中文验收场景(client: TestClient) -> None:
    headers = _leader_headers(client)
    activity = _activity(client, headers, quota=1)

    response = client.get(f"/api/v1/activities/{activity['id']}/registration-risk-smoke-panel", headers=headers)

    assert response.status_code == 200
    scenarios = response.json()['data']['scenarios']
    assert [item['title'] for item in scenarios] == ['正常报名', '超出名额', '重复报名', '取消后重新报名']
    assert all({'test_data', 'steps', 'expected_result', 'failure_hint'} <= set(item) for item in scenarios)
