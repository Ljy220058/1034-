from __future__ import annotations

from pathlib import Path

import pytest

import backend.database as database
from tests.test_api import _auth_header, _client, _register_member


@pytest.fixture()
def client(tmp_path: Path):
    return _client(tmp_path)


def _leader_and_member(client):
    leader = _register_member(client, name='Leader', phone='15550001001')
    member = _register_member(client, name='Runner', phone='15550001002')
    with database.connect() as connection:
        connection.execute('UPDATE members SET role = ? WHERE id = ?', ('leader', leader['member']['id']))
    leader_token = client.post('/api/v1/auth/login', json={'phone': '15550001001', 'password': 'secret123'}).json()['data']['access_token']
    return leader, member, _auth_header(leader_token)


def _activity_with_registration(client):
    leader, member, leader_headers = _leader_and_member(client)
    activity = client.post(
        '/api/v1/activities',
        json={'title': 'Check-in Run', 'start_time': '2026-06-07T07:00:00+00:00', 'location': 'Track'},
        headers=leader_headers,
    ).json()['data']
    reg = client.post(
        f"/api/v1/activities/{activity['id']}/registrations",
        json={'member_id': member['member']['id']},
        headers=_auth_header(member['access_token']),
    )
    assert reg.status_code == 201
    return leader, member, activity, leader_headers


def test_checkin_create_contract_and_idempotency(client):
    _, member, activity, _ = _activity_with_registration(client)
    member_headers = _auth_header(member['access_token'])

    payload = {'member_id': member['member']['id'], 'checked_in_at': '2026-06-07T07:05:00+00:00', 'gps_checked': True}
    resp = client.post(f"/api/v1/activities/{activity['id']}/checkins", json=payload, headers=member_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body == {'data': body['data']}
    data = body['data']
    assert data['activity_id'] == activity['id']
    assert data['member_id'] == member['member']['id']
    assert data['status'] == 'signed_in'
    assert data['gps_checked'] is True
    assert data['signed_in_at'] == '2026-06-07T07:05:00+00:00'
    assert isinstance(data['id'], int)

    repeat = client.post(
        f"/api/v1/activities/{activity['id']}/checkins",
        json={'member_id': member['member']['id'], 'gps_checked': False},
        headers=member_headers,
    )
    assert repeat.status_code == 201
    repeat_data = repeat.json()['data']
    assert repeat_data['id'] == data['id']
    assert repeat_data['gps_checked'] is False
    assert repeat_data['signed_in_at'] == data['signed_in_at']


def test_checkin_create_permissions_and_validation(client):
    _, member, activity, _ = _activity_with_registration(client)
    member_headers = _auth_header(member['access_token'])
    outsider = _register_member(client, name='Outsider', phone='15550001003')
    outsider_headers = _auth_header(outsider['access_token'])

    forbidden = client.post(
        f"/api/v1/activities/{activity['id']}/checkins",
        json={'member_id': member['member']['id']},
        headers=outsider_headers,
    )
    assert forbidden.status_code == 403

    unregistered = client.post(
        f"/api/v1/activities/{activity['id']}/checkins",
        json={'member_id': outsider['member']['id']},
        headers=outsider_headers,
    )
    assert unregistered.status_code == 409
    assert unregistered.json() == {'detail': 'member is not registered for this activity'}

    wrong_member = client.post(
        f"/api/v1/activities/{activity['id']}/checkins",
        json={'member_id': outsider['member']['id']},
        headers=member_headers,
    )
    assert wrong_member.status_code == 403

    missing_member = client.post(
        f"/api/v1/activities/{activity['id']}/checkins",
        json={'member_id': 999999},
        headers=member_headers,
    )
    assert missing_member.status_code == 404
    assert missing_member.json() == {'detail': 'activity or member not found'}

    invalid = client.post(
        f"/api/v1/activities/{activity['id']}/checkins",
        json={'member_id': member['member']['id'], 'checked_in_at': 'not-a-time'},
        headers=member_headers,
    )
    assert invalid.status_code == 422
    assert any(err['loc'][-1] == 'checked_in_at' for err in invalid.json()['detail'])


def test_checkin_list_detail_delete_permissions_and_missing_cases(client):
    leader, member, activity, leader_headers = _activity_with_registration(client)
    member_headers = _auth_header(member['access_token'])
    attendance = client.post(
        f"/api/v1/activities/{activity['id']}/checkins",
        json={'member_id': member['member']['id']},
        headers=member_headers,
    ).json()['data']

    list_forbidden = client.get(f"/api/v1/activities/{activity['id']}/checkins", headers=member_headers)
    assert list_forbidden.status_code == 403

    list_resp = client.get(f"/api/v1/activities/{activity['id']}/checkins", headers=leader_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()['data'][0]['id'] == attendance['id']

    detail_forbidden = client.get(f"/api/v1/activities/{activity['id']}/checkins/{attendance['id']}", headers=member_headers)
    assert detail_forbidden.status_code == 403

    detail_resp = client.get(f"/api/v1/activities/{activity['id']}/checkins/{attendance['id']}", headers=leader_headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()['data'] == attendance

    missing_activity_detail = client.get('/api/v1/activities/999/checkins/1', headers=leader_headers)
    assert missing_activity_detail.status_code == 404
    assert missing_activity_detail.json() == {'detail': 'attendance not found'}

    delete_forbidden = client.delete(f"/api/v1/activities/{activity['id']}/checkins/{attendance['id']}", headers=member_headers)
    assert delete_forbidden.status_code == 403

    delete_resp = client.delete(f"/api/v1/activities/{activity['id']}/checkins/{attendance['id']}", headers=leader_headers)
    assert delete_resp.status_code == 200
    assert delete_resp.json() == {'data': {'deleted': True}}

    delete_again = client.delete(f"/api/v1/activities/{activity['id']}/checkins/{attendance['id']}", headers=leader_headers)
    assert delete_again.status_code == 404
    assert delete_again.json() == {'detail': 'attendance not found'}
