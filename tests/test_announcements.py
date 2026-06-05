from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
import backend.database as database
import backend.db as db_module
from backend.db import initialize_database
from backend.settings import Settings


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        project_root=Path('/root/autodl-tmp/projects/hermes-swarm-lab'),
        workspace_root=Path('/root/autodl-tmp/projects/hermes-swarm-lab'),
        database_path=tmp_path / 'test.db',
    )


def test_announcement_crud(monkeypatch, tmp_path):
    settings = make_settings(tmp_path)
    monkeypatch.setattr('backend.settings.get_settings', lambda: settings)
    monkeypatch.setattr('backend.db.get_settings', lambda: settings)
    initialize_database(settings)

    client = TestClient(app)
    create_auth = client.post('/api/v1/auth/register', json={'name': 'Admin', 'phone': '15550001111', 'password': 'secret123', 'role': 'member'})
    assert create_auth.status_code == 201
    with database.connect() as connection:
        connection.execute('UPDATE members SET role = ? WHERE phone = ?', ('admin', '15550001111'))
    login_auth = client.post('/api/v1/auth/login', json={'phone': '15550001111', 'password': 'secret123'})
    assert login_auth.status_code == 200
    headers = {'Authorization': f"Bearer {login_auth.json()['data']['access_token']}"}

    create_resp = client.post('/api/v1/announcements', json={'title': '团长通知', 'body': '周六晨跑照常举行'}, headers=headers)
    assert create_resp.status_code == 201
    created = create_resp.json()['data']
    assert created['title'] == '团长通知'
    assert created['status'] == 'published'
    assert created['is_pinned'] is True

    list_resp = client.get('/api/v1/announcements', headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()['data']
    assert len(items) == 1
    assert items[0]['id'] == created['id']

    detail_resp = client.get(f"/api/v1/announcements/{created['id']}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()['data']['body'] == '周六晨跑照常举行'

    patch_resp = client.patch(f"/api/v1/announcements/{created['id']}", json={'body': '周六晨跑改为雨天备选方案'}, headers=headers)
    assert patch_resp.status_code == 200
    assert patch_resp.json()['data']['body'] == '周六晨跑改为雨天备选方案'

    delete_resp = client.delete(f"/api/v1/announcements/{created['id']}", headers=headers)
    assert delete_resp.status_code == 200
    assert delete_resp.json()['data']['deleted'] is True

    missing_resp = client.get(f"/api/v1/announcements/{created['id']}", headers=headers)
    assert missing_resp.status_code == 404


def test_announcement_validation(monkeypatch, tmp_path):
    settings = make_settings(tmp_path)
    monkeypatch.setattr('backend.settings.get_settings', lambda: settings)
    monkeypatch.setattr('backend.db.get_settings', lambda: settings)
    initialize_database(settings)

    client = TestClient(app)
    create_auth = client.post('/api/v1/auth/register', json={'name': 'Admin', 'phone': '15550001112', 'password': 'secret123', 'role': 'member'})
    assert create_auth.status_code == 201
    with database.connect() as connection:
        connection.execute('UPDATE members SET role = ? WHERE phone = ?', ('admin', '15550001112'))
    login_auth = client.post('/api/v1/auth/login', json={'phone': '15550001112', 'password': 'secret123'})
    assert login_auth.status_code == 200
    headers = {'Authorization': f"Bearer {login_auth.json()['data']['access_token']}"}

    resp = client.post('/api/v1/announcements', json={'title': '', 'body': 'x'}, headers=headers)
    assert resp.status_code == 422
