from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.database import SCHEMA_SQL, connect, init_db


@pytest.fixture()
def temp_db(monkeypatch, tmp_path: Path):
    """为每个测试创建独立临时数据库。"""
    db_path = tmp_path / 'test.db'
    monkeypatch.setenv('RUNNING_CLUB_DB_PATH', str(db_path))
    init_db(db_path)
    with connect(db_path) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS running_import_consents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                read_fields TEXT NOT NULL,
                consent_version TEXT NOT NULL,
                granted_at TEXT NOT NULL,
                revoked_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
    return db_path


@pytest.fixture()
def client(temp_db):
    """使用临时数据库的 FastAPI 测试客户端。"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def seeded_member_id(temp_db):
    """插入一个可用于授权测试的普通成员。"""
    with connect(temp_db) as connection:
        cursor = connection.execute(
            """
            INSERT INTO members (name, phone, role, running_years, pace, usual_distance_km, training_goal, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ('Seed Member', '13800000011', 'member', 2, '5:30', 10.0, 'keep running', 'hash'),
        )
    return cursor.lastrowid


@pytest.fixture()
def auth_headers(client, seeded_member_id):
    """伪造当前成员认证头以通过依赖注入。"""
    import backend.routes.running_data_imports as routes

    member_id = seeded_member_id

    def fake_current_user():
        return routes.CurrentUser(id=member_id, role='member', member={'id': member_id})

    app.dependency_overrides[routes.get_current_user] = fake_current_user
    return {'Authorization': 'Bearer test-token'}


@pytest.fixture()
def cleanup_auth_override():
    yield
    import backend.routes.running_data_imports as routes
    app.dependency_overrides.pop(routes.get_current_user, None)


def test_running_data_imports_precheck_正常输入_返回授权信息(client, auth_headers, cleanup_auth_override):
    """预检接口在正常输入下返回 source 与 precheck_id。"""
    resp = client.get('/api/v1/running-data-imports/precheck?source=manual_file', headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()['data']['consent_artifact']['precheck_id'] == 'running-data-imports:manual_file:v1'


def test_running_data_imports_precheck_未认证_返回401(client, cleanup_auth_override):
    """预检接口在未携带认证时返回 401。"""
    resp = client.get('/api/v1/running-data-imports/precheck?source=manual_file')
    assert resp.status_code == 401


def test_running_data_imports_precheck_缺少必填参数_返回422(client, auth_headers, cleanup_auth_override):
    """预检接口缺少 source 时返回 422。"""
    resp = client.get('/api/v1/running-data-imports/precheck', headers=auth_headers)
    assert resp.status_code == 422


def test_running_data_imports_consent_正常输入_返回201(client, auth_headers, cleanup_auth_override):
    """授权创建在正常输入下返回 201。"""
    resp = client.post('/api/v1/running-data-imports/consent', json={
        'source': 'manual_file',
        'read_fields': ['title', 'start_time'],
        'consent_version': 'v1',
    }, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()['data']['consent']['source'] == 'manual_file'


def test_running_data_imports_consent_缺少必填字段_返回422(client, auth_headers, cleanup_auth_override):
    """授权创建缺少 read_fields 时返回 422。"""
    resp = client.post('/api/v1/running-data-imports/consent', json={'source': 'manual_file', 'consent_version': 'v1'}, headers=auth_headers)
    assert resp.status_code == 422


def test_running_data_imports_consent_未认证_返回401(client, cleanup_auth_override):
    """授权创建在未认证时返回 401。"""
    resp = client.post('/api/v1/running-data-imports/consent', json={'source': 'manual_file', 'read_fields': ['title'], 'consent_version': 'v1'})
    assert resp.status_code == 401


def test_running_data_imports_start_未授权_返回403(client, auth_headers, cleanup_auth_override):
    """开始导入前未创建授权时返回 403。"""
    resp = client.post('/api/v1/running-data-imports/start', json={
        'source': 'manual_file',
        'consent_acknowledged': True,
        'precheck_id': 'running-data-imports:manual_file:v1',
        'scope_version': 'running-data-imports.v1',
    }, headers=auth_headers)
    assert resp.status_code == 403


def test_running_data_imports_start_已授权_返回202(client, auth_headers, cleanup_auth_override):
    """已授权且预检匹配时开始导入返回 202。"""
    client.post('/api/v1/running-data-imports/consent', json={'source': 'manual_file', 'read_fields': ['title'], 'consent_version': 'v1'}, headers=auth_headers)
    resp = client.post('/api/v1/running-data-imports/start', json={
        'source': 'manual_file',
        'consent_acknowledged': True,
        'precheck_id': 'running-data-imports:manual_file:v1',
        'scope_version': 'running-data-imports.v1',
    }, headers=auth_headers)
    assert resp.status_code == 202


def test_running_data_imports_wizard_csv_正常输入_返回预览(client, auth_headers, cleanup_auth_override):
    """CSV 向导在正常输入下返回预览数据。"""
    resp = client.post('/api/v1/running-data-imports/wizard', json={
        'source': 'manual_file', 'format': 'csv', 'content': 'title,start_time,distance_km,duration_seconds\nRun,2026-06-09T07:00:00+00:00,5.2,1800',
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()['data']['input_format'] == 'csv'


def test_running_data_imports_wizard_json_缺少必填字段_返回422(client, auth_headers, cleanup_auth_override):
    """JSON 向导缺少 content 时返回 422。"""
    resp = client.post('/api/v1/running-data-imports/wizard', json={'source': 'manual_file', 'format': 'json'}, headers=auth_headers)
    assert resp.status_code == 422
