from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app import app
from backend.db import initialize_database
from backend.repository import reset_database
from conftest import make_auth_headers

client = TestClient(app)


def setup_function() -> None:
    """重置测试数据，避免用例互相污染。"""
    reset_database()
    initialize_database()
    client.post(
        '/api/v1/members',
        json={
            'name': '种子管理员',
            'phone': '19900000001',
            'role': 'admin',
            'running_years': 3,
            'pace': '5:30',
            'usual_distance_km': 12,
            'training_goal': '测试用',
            'password': 'password123',
        },
        headers={'Authorization': 'Bearer role:admin'},
    )


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
        headers={'Authorization': make_auth_headers(client, '19900000001', 'leader')['Authorization']},
    )
    assert response.status_code == 201
    return response.json()['data']['id']


def _create_member(name: str, phone: str) -> int:
    response = client.post(
        '/api/v1/members',
        json={
            'name': name,
            'phone': phone,
            'role': 'member',
            'running_years': 2,
            'pace': '5:45',
            'usual_distance_km': 10,
            'training_goal': '完成半马',
        },
        headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
    )
    assert response.status_code == 201
    return response.json()['data']['id']


def _register(activity_id: int, member_id: int) -> None:
    response = client.post(
        f'/api/v1/activities/{activity_id}/registrations',
        json={'member_id': member_id},
        headers={'Authorization': make_auth_headers(client, '19900000001', 'leader')['Authorization']},
    )
    assert response.status_code == 201


def _checkin(activity_id: int, member_id: int, token: str) -> None:
    response = client.post(
        f'/api/v1/activities/{activity_id}/checkins',
        json={'member_id': member_id},
        headers={'Authorization': token},
    )
    assert response.status_code == 201


def test_activity_digest_empty_registration_returns_structured_json() -> None:
    activity_id = _create_activity()

    response = client.get(f'/api/v1/activities/{activity_id}/digest', headers={'Authorization': make_auth_headers(client, '19900000001', 'member')['Authorization']})

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['activity']['id'] == activity_id
    assert payload['data']['overview']['registered_count'] == 0
    assert payload['data']['overview']['signed_in_count'] == 0
    assert payload['data']['overview']['absent_count'] == 0
    assert payload['data']['absent_members'] == []
    assert isinstance(payload['data']['follow_up_suggestions'], list)


def test_activity_digest_full_attendance_has_no_absent_members() -> None:
    activity_id = _create_activity()
    member_id = _create_member('李雷', '13800000001')
    _register(activity_id, member_id)
    _checkin(activity_id, member_id, make_auth_headers(client, '19900000001', 'member')['Authorization'])

    response = client.get(f'/api/v1/activities/{activity_id}/digest', headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']})

    assert response.status_code == 200
    payload = response.json()
    assert payload['data']['overview']['registered_count'] >= 1
    assert payload['data']['overview']['signed_in_count'] >= 0
    assert payload['data']['overview']['absent_count'] == 0
    assert payload['data']['absent_members'] == []
    assert payload['data']['feedback_summary']


def test_activity_digest_includes_absent_member_list() -> None:
    activity_id = _create_activity()
    member_id = _create_member('王芳', '13800000002')
    _register(activity_id, member_id)

    response = client.get(f'/api/v1/activities/{activity_id}/digest', headers={'Authorization': make_auth_headers(client, '19900000001', 'leader')['Authorization']})

    assert response.status_code == 200
    payload = response.json()
    assert payload['data']['overview']['registered_count'] >= 1
    assert payload['data']['overview']['signed_in_count'] == 0
    assert payload['data']['overview']['absent_count'] == 1
    assert payload['data']['absent_members'] == [{'member_id': member_id, 'name': '王芳'}]
    assert payload['data']['feedback_summary']
