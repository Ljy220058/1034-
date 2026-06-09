from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app


def _client(tmp_path: Path) -> TestClient:
    database.init_db(tmp_path / 'test.db')
    return TestClient(app, raise_server_exceptions=False)


def _register_member(client: TestClient, *, phone: str, role: str = 'member') -> dict[str, str]:
    response = client.post(
        '/api/v1/auth/register',
        json={'name': 'Privacy Runner', 'phone': phone, 'password': 'secret123', 'role': role},
    )
    assert response.status_code == 201
    return response.json()['data']


def _auth_header(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def test_running_data_import_precheck_正常输入_返回授权说明(tmp_path: Path) -> None:
    """预检接口对合法 source 返回授权说明与保存边界。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900003001')

    response = client.get('/api/v1/running-data-imports/precheck', params={'source': 'garmin'}, headers=_auth_header(member['access_token']))

    assert response.status_code == 200
    assert response.json()['data']['source'] == {'id': 'garmin', 'name': '佳明'}


def test_running_data_import_precheck_缺少source_返回422(tmp_path: Path) -> None:
    """预检接口缺少必填 source 时返回 422。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900003002')

    response = client.get('/api/v1/running-data-imports/precheck', headers=_auth_header(member['access_token']))

    assert response.status_code == 422
    assert 'source' in str(response.json()['detail'])


def test_running_data_import_precheck_未认证_返回401(tmp_path: Path) -> None:
    """预检接口未携带 token 时返回 401。"""
    client = _client(tmp_path)

    response = client.get('/api/v1/running-data-imports/precheck', params={'source': 'garmin'})

    assert response.status_code == 401


def test_running_data_import_start_未授权_返回403(tmp_path: Path) -> None:
    """开始导入前未确认授权范围时拒绝请求。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900003003')

    response = client.post('/api/v1/running-data-imports/start', json={'source': 'garmin', 'consent_acknowledged': False}, headers=_auth_header(member['access_token']))

    assert response.status_code == 403
    assert response.json()['detail'] == '跑步数据导入需要先确认授权范围'


def test_running_data_import_start_预检不匹配_返回403(tmp_path: Path) -> None:
    """开始导入时 precheck_id 不匹配会被拒绝。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900003004')

    response = client.post(
        '/api/v1/running-data-imports/start',
        json={'source': 'garmin', 'consent_acknowledged': True, 'precheck_id': 'running-data-imports:coros:v1', 'scope_version': 'running-data-imports.v1'},
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 403
    assert response.json()['detail'] == '跑步数据导入需要匹配的预检确认记录'


def test_running_data_import_start_授权后返回202(tmp_path: Path) -> None:
    """完成授权后开始导入返回 202 且不直接写入数据。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900003005')
    consent = client.post('/api/v1/running-data-imports/consent', json={'source': 'garmin', 'read_fields': ['gps_track_summary'], 'consent_version': 'v1'}, headers=_auth_header(member['access_token']))
    assert consent.status_code == 201

    response = client.post(
        '/api/v1/running-data-imports/start',
        json={'source': 'garmin', 'consent_acknowledged': True, 'precheck_id': 'running-data-imports:garmin:v1', 'scope_version': 'running-data-imports.v1'},
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 202
    assert response.json()['data']['import_started'] is False


def test_running_data_import_consent_缺少读取字段_返回422(tmp_path: Path) -> None:
    """授权接口 read_fields 为空时返回 422。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900003006')

    response = client.post('/api/v1/running-data-imports/consent', json={'source': 'garmin', 'read_fields': [], 'consent_version': 'v1'}, headers=_auth_header(member['access_token']))

    assert response.status_code == 422
    assert 'read_fields cannot be empty' in str(response.json()['detail'])


def test_running_data_import_consent_未认证_返回401(tmp_path: Path) -> None:
    """授权接口未登录时返回 401。"""
    client = _client(tmp_path)

    response = client.post('/api/v1/running-data-imports/consent', json={'source': 'garmin', 'read_fields': ['gps_track_summary'], 'consent_version': 'v1'})

    assert response.status_code == 401


def test_running_data_import_consent_敏感字段_返回422(tmp_path: Path) -> None:
    """授权接口会拒绝敏感字段组合。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900003007')

    response = client.post('/api/v1/running-data-imports/consent', json={'source': 'garmin', 'read_fields': ['access_token', 'gps_track_summary'], 'consent_version': 'v1'}, headers=_auth_header(member['access_token']))

    assert response.status_code == 422
    assert 'access_token' in response.json()['detail']


def test_running_data_import_consent_撤销后再次开始返回403(tmp_path: Path) -> None:
    """授权被撤销后再次开始导入时返回 403。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900003008')
    consent = client.post('/api/v1/running-data-imports/consent', json={'source': 'garmin', 'read_fields': ['gps_track_summary'], 'consent_version': 'v1'}, headers=_auth_header(member['access_token']))
    assert consent.status_code == 201
    revoke = client.delete('/api/v1/running-data-imports/consent', params={'source': 'garmin'}, headers=_auth_header(member['access_token']))
    assert revoke.status_code == 200

    response = client.post(
        '/api/v1/running-data-imports/start',
        json={'source': 'garmin', 'consent_acknowledged': True, 'precheck_id': 'running-data-imports:garmin:v1', 'scope_version': 'running-data-imports.v1'},
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 403
    assert response.json()['detail'] == '该数据源尚未完成有效授权或授权已撤销'
