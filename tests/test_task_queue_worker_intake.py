from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
import os
import traceback

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app



def _client(tmp_path):
    database.init_db(tmp_path / 'test.db')
    return TestClient(app, raise_server_exceptions=False)



def _register_and_login(client: TestClient, phone: str, *, name: str = 'Runner') -> tuple[dict[str, object], str]:
    register = client.post(
        '/api/v1/auth/register',
        json={'name': name, 'phone': phone, 'password': 'secret123', 'role': 'member'},
    )
    assert register.status_code == 201
    member = register.json()['data']['member']
    token = client.post('/api/v1/auth/login', json={'phone': phone, 'password': 'secret123'}).json()['data']['access_token']
    return member, token



def _make_leader(client: TestClient, phone: str = '15550001001') -> str:
    unique_phone = f'{phone}-{uuid4().hex[:8]}'
    member, _ = _register_and_login(client, unique_phone, name='Leader')
    with database.connect() as connection:
        connection.execute('UPDATE members SET role = ? WHERE id = ?', ('leader', member['id']))
    return client.post('/api/v1/auth/login', json={'phone': unique_phone, 'password': 'secret123'}).json()['data']['access_token']



def _make_activity(client: TestClient, leader_token: str) -> dict[str, object]:
    response = client.post(
        '/api/v1/activities',
        json={
            'title': 'Morning Run',
            'start_time': '2026-06-07T07:00:00+00:00',
            'location': 'Track',
        },
        headers={'Authorization': f'Bearer {leader_token}'},
    )
    assert response.status_code == 201
    return response.json()['data']



def test_task_queue_worker_schema_exists(tmp_path) -> None:
    database.init_db(tmp_path / 'test.db')

    with database.connect() as connection:
        row = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'task_queue_workers'").fetchone()
        columns = connection.execute('PRAGMA table_info(task_queue_workers)').fetchall()

    assert row is not None
    assert [column['name'] for column in columns] == [
        'id',
        'worker_key',
        'name',
        'status',
        'capabilities',
        'last_seen_at',
        'created_at',
        'updated_at',
    ]



def test_worker_intake_creates_and_updates_persistence(tmp_path) -> None:
    client = _client(tmp_path)
    leader_token = _make_leader(client)

    first = client.post(
        '/api/v1/workers/intake',
        json={
            'worker_key': 'worker-alpha',
            'name': 'Alpha Worker',
            'status': 'active',
            'capabilities': ['intake', 'verify'],
        },
        headers={'Authorization': f'Bearer {leader_token}'},
    )
    assert first.status_code == 201
    first_data = first.json()['data']
    assert first_data['worker_key'] == 'worker-alpha'
    assert first_data['name'] == 'Alpha Worker'
    assert first_data['status'] == 'active'
    assert first_data['capabilities'] == ['intake', 'verify']

    second = client.post(
        '/api/v1/workers/intake',
        json={
            'worker_key': 'worker-alpha',
            'name': 'Alpha Worker Renamed',
            'status': 'paused',
            'capabilities': ['verify'],
        },
        headers={'Authorization': f'Bearer {leader_token}'},
    )
    assert second.status_code == 201
    second_data = second.json()['data']
    assert second_data['id'] == first_data['id']
    assert second_data['name'] == 'Alpha Worker Renamed'
    assert second_data['status'] == 'paused'
    assert second_data['capabilities'] == ['verify']

    with database.connect() as connection:
        row = connection.execute('SELECT worker_key, name, status, capabilities FROM task_queue_workers WHERE worker_key = ?', ('worker-alpha',)).fetchone()
    assert row['name'] == 'Alpha Worker Renamed'
    assert row['status'] == 'paused'
    assert row['capabilities'] == '["verify"]'



def test_worker_intake_rejects_bad_status_and_missing_auth(tmp_path) -> None:
    client = _client(tmp_path)

    unauthorized = client.post(
        '/api/v1/workers/intake',
        json={'worker_key': 'worker-beta', 'name': 'Beta Worker', 'status': 'active'},
    )
    assert unauthorized.status_code == 401

    leader_token = _make_leader(client)
    invalid = client.post(
        '/api/v1/workers/intake',
        json={'worker_key': 'worker-beta', 'name': 'Beta Worker', 'status': 'sleeping'},
        headers={'Authorization': f'Bearer {leader_token}'},
    )
    assert invalid.status_code == 422


def test_auth_register_failure_is_reproducible_with_unique_phone(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('PYTHONFAULTHANDLER', '1')
    client = _client(tmp_path)
    phone = f'15550001001-{uuid4().hex[:8]}'
    response = client.post(
        '/api/v1/auth/register',
        json={'name': 'Leader', 'phone': phone, 'password': 'secret123', 'role': 'member'},
    )
    assert response.status_code == 201, response.text
