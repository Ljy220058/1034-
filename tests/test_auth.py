from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app


def _client(tmp_path: Path):
    db_path = tmp_path / 'test.db'
    database.init_db(db_path)
    return TestClient(app)


def _auth_header(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def _register_member(client: TestClient, *, name: str, phone: str, role: str = 'member') -> dict:
    resp = client.post(
        '/api/v1/auth/register',
        json={'name': name, 'phone': phone, 'password': 'secret123', 'role': role},
    )
    assert resp.status_code == 201
    return resp.json()['data']


def test_auth_registration_and_login(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = _register_member(client, name='Alice', phone='13800000000')

    assert created['token_type'] == 'Bearer'
    assert created['member']['name'] == 'Alice'
    assert 'password_hash' not in created['member']

    login = client.post('/api/v1/auth/login', json={'phone': '13800000000', 'password': 'secret123'})
    assert login.status_code == 200
    assert login.json()['data']['member']['phone'] == '13800000000'

    duplicate = client.post('/api/v1/auth/register', json={'name': 'Alice 2', 'phone': '13800000000', 'password': 'secret123'})
    assert duplicate.status_code == 409


def test_auth_rejects_role_escalation_on_register(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post('/api/v1/auth/register', json={'name': 'Boss', 'phone': '13800000001', 'password': 'secret123', 'role': 'admin'})
    assert resp.status_code == 403
    assert resp.json() == {'detail': 'role escalation is not allowed'}


def test_auth_login_contract_and_edge_cases(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client, name='Runner', phone='13800000009')

    wrong_password = client.post('/api/v1/auth/login', json={'phone': '13800000009', 'password': 'wrongpass'})
    assert wrong_password.status_code == 401
    assert wrong_password.json() == {'detail': 'invalid phone or password'}

    missing_phone = client.post('/api/v1/auth/login', json={'phone': '13800000010', 'password': 'secret123'})
    assert missing_phone.status_code == 401
    assert missing_phone.json() == {'detail': 'invalid phone or password'}

    token_payload = member['access_token'].split(':', 2)
    assert len(token_payload) == 3
    member_id, role, expires_at = token_payload
    assert member_id.isdigit()
    assert role == 'member'
    assert 'T' in expires_at

    me = client.get('/api/v1/members/me', headers=_auth_header(member['access_token']))
    assert me.status_code == 200
    assert me.json()['data']['phone'] == '13800000009'


def test_authenticated_membership_and_self_service(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client, name='Alice', phone='13800000002')
    headers = _auth_header(member['access_token'])

    assert client.get('/api/v1/members/me', headers=headers).status_code == 200
    assert client.get('/api/v1/members', headers=headers).status_code == 403
    assert client.post('/api/v1/members', json={'name': 'X'}, headers=headers).status_code == 403

    self_update = client.patch(f"/api/v1/members/{member['member']['id']}", json={'name': 'Alice Updated'}, headers=headers)
    assert self_update.status_code == 200
    assert self_update.json()['data']['name'] == 'Alice Updated'

    forbidden_update = client.patch('/api/v1/members/999', json={'name': 'Nope'}, headers=headers)
    assert forbidden_update.status_code == 403


def test_admin_can_manage_members_but_cannot_escalate_roles_via_body(tmp_path: Path) -> None:
    client = _client(tmp_path)
    admin_resp = client.post('/api/v1/auth/register', json={'name': 'Admin', 'phone': '13800000003', 'password': 'secret123'})
    assert admin_resp.status_code == 201
    admin = admin_resp.json()['data']
    headers = _auth_header(admin['access_token'])

    created = client.post('/api/v1/members', json={'name': 'Bob', 'phone': '13800000004', 'role': 'member', 'running_years': 2}, headers=headers)
    assert created.status_code == 201
    assert created.json()['data']['role'] == 'member'

    escalation = client.post('/api/v1/members', json={'name': 'Eve', 'phone': '13800000005', 'role': 'admin'}, headers=headers)
    assert escalation.status_code == 403

    role_change = client.patch(f"/api/v1/members/{created.json()['data']['id']}", json={'role': 'leader'}, headers=headers)
    assert role_change.status_code == 200
    assert role_change.json()['data']['role'] == 'leader'

    deleted = client.delete(f"/api/v1/members/{created.json()['data']['id']}", headers=headers)
    assert deleted.status_code == 200


def test_public_read_routes_and_admin_mutations(tmp_path: Path) -> None:
    client = _client(tmp_path)
    admin_resp = client.post('/api/v1/auth/register', json={'name': 'Admin', 'phone': '13800000006', 'password': 'secret123'})
    assert admin_resp.status_code == 201
    admin = admin_resp.json()['data']
    headers = _auth_header(admin['access_token'])

    activity = client.post('/api/v1/activities', json={'title': 'Sunday Run', 'start_time': '2026-06-07T07:00:00+00:00', 'location': 'Park'}, headers=headers)
    assert activity.status_code == 201
    activity_id = activity.json()['data']['id']

    announcement = client.post('/api/v1/announcements', json={'title': 'Notice', 'body': 'Hello'}, headers=headers)
    assert announcement.status_code == 201
    announcement_id = announcement.json()['data']['id']

    assert client.get('/api/v1/activities').status_code == 200
    assert client.get('/api/v1/announcements').status_code == 200
    assert client.get(f'/api/v1/activities/{activity_id}').status_code == 200
    assert client.get(f'/api/v1/announcements/{announcement_id}').status_code == 200

    assert client.patch(f'/api/v1/activities/{activity_id}', json={'location': 'Trail'}, headers=headers).status_code == 200
    assert client.patch(f'/api/v1/announcements/{announcement_id}', json={'body': 'Updated'}, headers=headers).status_code == 200
    assert client.delete(f'/api/v1/activities/{activity_id}', headers=headers).status_code == 200
    assert client.delete(f'/api/v1/announcements/{announcement_id}', headers=headers).status_code == 200


def test_registration_self_service_and_forbidden_others(tmp_path: Path) -> None:
    client = _client(tmp_path)
    admin_resp = client.post('/api/v1/auth/register', json={'name': 'Admin', 'phone': '13800000007', 'password': 'secret123'})
    assert admin_resp.status_code == 201
    admin = admin_resp.json()['data']
    member = _register_member(client, name='Alice', phone='13800000008')
    member_headers = _auth_header(member['access_token'])
    admin_headers = _auth_header(admin['access_token'])

    activity = client.post('/api/v1/activities', json={'title': 'Run', 'start_time': '2026-06-07T07:00:00+00:00', 'location': 'Park'}, headers=admin_headers).json()['data']

    own = client.post(f"/api/v1/activities/{activity['id']}/registrations", json={'member_id': member['member']['id']}, headers=member_headers)
    assert own.status_code == 201

    other = client.post(f"/api/v1/activities/{activity['id']}/registrations", json={'member_id': admin['member']['id']}, headers=member_headers)
    assert other.status_code == 403

    cancel_other = client.delete(f"/api/v1/activities/{activity['id']}/registrations/{admin['member']['id']}", headers=member_headers)
    assert cancel_other.status_code == 403

    cancel_own = client.delete(f"/api/v1/activities/{activity['id']}/registrations/{member['member']['id']}", headers=member_headers)
    assert cancel_own.status_code == 200


def test_unauthenticated_requests_are_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)
    endpoints = [
        ('get', '/api/v1/members', None),
        ('post', '/api/v1/members', {'name': 'x'}),
        ('get', '/api/v1/members/me', None),
        ('patch', '/api/v1/members/1', {'name': 'x'}),
        ('delete', '/api/v1/members/1', None),
        ('post', '/api/v1/announcements', {'title': 'x', 'body': 'x'}),
        ('patch', '/api/v1/announcements/1', {'body': 'x'}),
        ('delete', '/api/v1/announcements/1', None),
        ('post', '/api/v1/activities', {'title': 'x', 'start_time': '2026-06-07T07:00:00+00:00', 'location': 'Park'}),
        ('patch', '/api/v1/activities/1', {'title': 'x'}),
        ('delete', '/api/v1/activities/1', None),
        ('post', '/api/v1/activities/1/registrations', {'member_id': 1}),
        ('delete', '/api/v1/activities/1/registrations/1', None),
    ]
    for method, url, payload in endpoints:
        kwargs = {'json': payload} if payload is not None else {}
        response = getattr(client, method)(url, **kwargs)
        assert response.status_code == 401

