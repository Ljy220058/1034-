from __future__ import annotations

from backend.app import app
from backend.db import initialize_database
from backend.repository import reset_database
from fastapi.testclient import TestClient

client = TestClient(app)


def setup_function() -> None:
    """重置测试数据，避免用例互相污染。"""
    reset_database()
    initialize_database()


def _create_member(name: str, phone: str, role: str = 'member') -> int:
    response = client.post(
        '/api/v1/auth/register',
        json={
            'name': name,
            'phone': phone,
            'password': 'secret123',
            'role': role,
            'running_years': 2,
            'pace': '5:45',
            'usual_distance_km': 10,
            'training_goal': '完成半马',
        },
    )
    assert response.status_code == 201
    if role != 'member':
        from backend.database import connect

        with connect() as connection:
            connection.execute('UPDATE members SET role = ? WHERE phone = ?', (role, phone))
    return response.json()['data']['member']['id']


def _login(phone: str) -> dict[str, str]:
    response = client.post('/api/v1/auth/login', json={'phone': phone, 'password': 'secret123'})
    assert response.status_code == 200
    return {'Authorization': f"Bearer {response.json()['data']['access_token']}"}


def _create_activity() -> int:
    response = client.post(
        '/api/v1/activities',
        json={
            'title': '周末长跑',
            'start_time': '2026-06-06T08:00:00+00:00',
            'location': '人民公园',
            'route': '环湖 8km',
            'distance_km': 8,
            'pace_group': '5:30-6:00',
            'description': '本周活动',
        },
        headers=_login('19900000001'),
    )
    assert response.status_code == 201
    return response.json()['data']['id']


def _register(activity_id: int, member_id: int) -> None:
    response = client.post(
        f'/api/v1/activities/{activity_id}/registrations',
        json={'member_id': member_id},
        headers=_login('19900000001'),
    )
    assert response.status_code == 201


def test_activity_list_includes_registration_status_for_logged_in_member() -> None:
    _create_member('管理员', '19900000001', 'leader')
    activity_id = _create_activity()
    member_id = _create_member('李雷', '13800000001')
    _register(activity_id, member_id)

    response = client.get('/api/v1/activities', headers=_login('13800000001'))

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert isinstance(payload['data'], list)
    target = next(item for item in payload['data'] if item['id'] == activity_id)
    assert target['registration_status'] == 'registered'
    assert target['is_registered'] is True


def test_activity_detail_defaults_to_not_registered_for_anonymous_user() -> None:
    _create_member('管理员', '19900000001', 'leader')
    activity_id = _create_activity()

    response = client.get(f'/api/v1/activities/{activity_id}')

    assert response.status_code == 200
    payload = response.json()
    assert payload['data']['registration_status'] == 'not_registered'
    assert payload['data']['is_registered'] is False


def test_activity_detail_returns_registered_status_for_logged_in_member() -> None:
    _create_member('管理员', '19900000001', 'leader')
    activity_id = _create_activity()
    member_id = _create_member('王芳', '13800000002')
    _register(activity_id, member_id)

    response = client.get(f'/api/v1/activities/{activity_id}', headers=_login('13800000002'))

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['id'] == activity_id
    assert payload['data']['registration_status'] == 'registered'
    assert payload['data']['is_registered'] is True


def test_activity_detail_missing_activity_returns_structured_error() -> None:
    response = client.get('/api/v1/activities/999999')

    assert response.status_code == 404
    assert response.json() == {'detail': 'activity not found'}
