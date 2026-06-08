from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app


def _client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / 'test.db'
    database.init_db(db_path)
    return TestClient(app)


def _register_member(client: TestClient, *, name: str, phone: str, role: str = 'member') -> dict:
    response = client.post(
        '/api/v1/auth/register',
        json={'name': name, 'phone': phone, 'password': 'secret123', 'role': role},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload['message'] == '成功'
    return payload['data']


def test_auth_registration_uses_strong_password_hash(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = _register_member(client, name='Alice', phone='13800000000')

    assert created['token_type'] == 'Bearer'
    assert created['member']['name'] == 'Alice'
    assert 'password_hash' not in created['member']

    with database.connect() as connection:
        row = connection.execute('SELECT password_hash FROM members WHERE phone = ?', ('13800000000',)).fetchone()
    assert row is not None
    assert row['password_hash'].startswith('$2b$') or row['password_hash'].startswith('pbkdf2_sha256$')


def test_auth_login_accepts_registration_password_and_returns_api_response(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _register_member(client, name='Runner', phone='13800000001')

    response = client.post('/api/v1/auth/login', json={'phone': '13800000001', 'password': 'secret123'})
    assert response.status_code == 200
    assert response.json()['message'] == '成功'
    assert response.json()['data']['member']['phone'] == '13800000001'


def test_auth_login_rejects_wrong_password_with_structured_error(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _register_member(client, name='Runner', phone='13800000002')

    response = client.post('/api/v1/auth/login', json={'phone': '13800000002', 'password': 'wrongpass'})
    assert response.status_code == 401
    assert response.json() == {'detail': 'invalid phone or password'}


def test_auth_login_upgrades_legacy_sha256_hash(tmp_path: Path) -> None:
    client = _client(tmp_path)
    legacy_hash = __import__('hashlib').sha256('secret123'.encode('utf-8')).hexdigest()
    with database.connect() as connection:
        connection.execute(
            'INSERT INTO members (name, phone, role, running_years, password_hash) VALUES (?, ?, ?, ?, ?)',
            ('Legacy', '13800000003', 'member', 0, legacy_hash),
        )

    response = client.post('/api/v1/auth/login', json={'phone': '13800000003', 'password': 'secret123'})
    assert response.status_code == 200
    assert response.json()['data']['member']['phone'] == '13800000003'

    with database.connect() as connection:
        row = connection.execute('SELECT password_hash FROM members WHERE phone = ?', ('13800000003',)).fetchone()
    assert row is not None
    assert row['password_hash'] != legacy_hash


def test_auth_login_wrong_password_does_not_upgrade_legacy_hash(tmp_path: Path) -> None:
    client = _client(tmp_path)
    legacy_hash = __import__('hashlib').sha256('secret123'.encode('utf-8')).hexdigest()
    with database.connect() as connection:
        connection.execute(
            'INSERT INTO members (name, phone, role, running_years, password_hash) VALUES (?, ?, ?, ?, ?)',
            ('Legacy', '13800000004', 'member', 0, legacy_hash),
        )

    response = client.post('/api/v1/auth/login', json={'phone': '13800000004', 'password': 'wrongpass'})
    assert response.status_code == 401
    assert response.json() == {'detail': 'invalid phone or password'}

    with database.connect() as connection:
        row = connection.execute('SELECT password_hash FROM members WHERE phone = ?', ('13800000004',)).fetchone()
    assert row is not None
    assert row['password_hash'] == legacy_hash
