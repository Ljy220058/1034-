from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app


def _client(tmp_path: Path) -> TestClient:
    database.init_db(tmp_path / 'test.db')
    return TestClient(app, raise_server_exceptions=False)


def _auth_header(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def _register_member(client: TestClient, *, phone: str) -> dict[str, Any]:
    response = client.post(
        '/api/v1/auth/register',
        json={'name': '导入测试员', 'phone': phone, 'password': 'secret123', 'role': 'member'},
    )
    assert response.status_code == 201
    return response.json()['data']


def _register_admin(client: TestClient, *, phone: str) -> dict[str, Any]:
    response = client.post(
        '/api/v1/auth/register',
        json={'name': '导入管理员', 'phone': phone, 'password': 'secret123', 'role': 'admin'},
    )
    assert response.status_code == 201
    return response.json()['data']

    data = response.json()['data']
    assert data['source'] == {'id': 'garmin', 'name': '佳明'}
    assert data['authorization_required'] is True
    assert data['can_start_import'] is False
    assert data['save_location']['table'] == 'running_data_imports'
    assert data['revocation'] == {'endpoint': '/api/v1/running-data-imports/consent', 'method': 'DELETE'}


def test_running_data_import_precheck_rejects_unsupported_source(tmp_path: Path) -> None:
    """不支持的数据源在预检入口返回 422。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004102')

    response = client.get('/api/v1/running-data-imports/precheck', params={'source': 'unknown_vendor'}, headers=_auth_header(member['access_token']))

    assert response.status_code == 422
    assert 'source must be one of' in str(response.json()['detail'])


def test_running_data_import_start_requires_explicit_consent(tmp_path: Path) -> None:
    """未确认授权范围时启动导入应返回 403。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004103')

    response = client.post('/api/v1/running-data-imports/start', json={'source': 'manual_file', 'consent_acknowledged': False}, headers=_auth_header(member['access_token']))

    assert response.status_code == 403
    assert response.json() == {'detail': '跑步数据导入需要先确认授权范围'}


def test_running_data_import_start_requires_matching_precheck_artifact(tmp_path: Path) -> None:
    """预检标识不匹配时启动导入应返回 403。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004104')

    response = client.post(
        '/api/v1/running-data-imports/start',
        json={'source': 'garmin', 'consent_acknowledged': True, 'precheck_id': 'running-data-imports:coros:v1', 'scope_version': 'running-data-imports.v1'},
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 403
    assert response.json() == {'detail': '跑步数据导入需要匹配的预检确认记录'}


def test_running_data_import_start_requires_matching_scope_version(tmp_path: Path) -> None:
    """授权版本不匹配时启动导入应返回 403。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004105')

    response = client.post(
        '/api/v1/running-data-imports/start',
        json={'source': 'garmin', 'consent_acknowledged': True, 'precheck_id': 'running-data-imports:garmin:v1', 'scope_version': 'running-data-imports.v2'},
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 403
    assert response.json() == {'detail': '跑步数据导入需要匹配的授权范围版本'}


def test_running_data_import_start_returns_safe_dry_run_when_authorized(tmp_path: Path) -> None:
    """授权完成后启动接口只返回安全的预检查结果，不真正导入。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004106')

    response = client.post(
        '/api/v1/running-data-imports/start',
        json={'source': 'manual_file', 'consent_acknowledged': True, 'precheck_id': 'running-data-imports:manual_file:v1', 'scope_version': 'running-data-imports.v1'},
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 202
    data = response.json()['data']
    assert data['status'] == 'authorized_precheck_only'
    assert data['import_started'] is False
    assert data['authorized_scope']['source'] == 'manual_file'
    assert data['next_step'] == 'frontend may request the real importer after showing the precheck panel'


def test_running_data_import_endpoints_reject_missing_auth(tmp_path: Path) -> None:
    """预检和启动接口在未登录时都应返回 401。"""
    client = _client(tmp_path)

    assert client.get('/api/v1/running-data-imports/precheck', params={'source': 'garmin'}).status_code == 401
    assert client.post('/api/v1/running-data-imports/start', json={'source': 'garmin', 'consent_acknowledged': True}).status_code == 401


def test_running_data_import_anomaly_precheck_requires_admin_permission(tmp_path: Path) -> None:
    """普通成员不能访问异常预检接口。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004107')

    response = client.post(
        '/api/v1/running-data-imports/anomaly-precheck',
        json={'source': 'generic', 'format': 'csv', 'content': 'title,start_time,duration_seconds,distance_meters,gps_track\n晨跑,2026-06-06 07:00:00,1800,5000,track_a'},
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 403
    assert response.json()['detail'] == 'forbidden'


def test_running_data_import_anomaly_precheck_rejects_invalid_csv_header(tmp_path: Path) -> None:
    """异常预检在 CSV 表头为空时返回 400。"""
    client = _client(tmp_path)
    admin = _register_admin(client, phone='13900004108')

    response = client.post('/api/v1/running-data-imports/anomaly-precheck', json={'source': 'generic', 'format': 'csv', 'content': '\n\n'}, headers=_auth_header(admin['access_token']))

    assert response.status_code == 400
    assert response.json() == {'detail': '无法解析 CSV 表头'}


def test_running_data_import_wizard_returns_preview_and_missing_fields(tmp_path: Path) -> None:
    """CSV 向导能返回字段映射、预览和缺失字段。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004109')

    response = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'generic', 'format': 'csv', 'content': '活动名称,开始时间,距离(km),用时(秒),地点\n晨跑,2026-06-01T07:00:10,5.2,1800,杭州\n'},
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['field_mapping']['title'] == '活动名称'
    assert data['missing_fields'] == []
    assert data['preview'][0]['title'] == '晨跑'


def test_running_data_import_wizard_requires_login_for_all_formats(tmp_path: Path) -> None:
    """未登录时 CSV 和 JSON 向导都应返回 401。"""
    client = _client(tmp_path)

    assert client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'csv', 'content': '活动名称,开始时间,距离(km),用时(秒)\n晨跑,2026-06-01T07:00:00,5,1800\n'}).status_code == 401
    assert client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'json', 'content': '[{"name":"晨跑","start_time":"2026-06-01T07:00:00","distance_km":5,"duration_seconds":1800}]'}).status_code == 401


def test_running_data_import_wizard_rejects_unsupported_source_with_422(tmp_path: Path) -> None:
    """非法来源在向导入口返回 422。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004110')

    response = client.post('/api/v1/running-data-imports/wizard', json={'source': 'unknown_vendor', 'format': 'csv', 'content': '活动名称,开始时间,距离(km),用时(秒)\n晨跑,2026-06-01T07:00:00,5,1800\n'}, headers=_auth_header(member['access_token']))

    assert response.status_code == 422
    assert 'source must be one of' in response.json()['detail']


def test_running_data_import_wizard_rejects_bad_json_with_chinese_detail(tmp_path: Path) -> None:
    """坏 JSON 会返回可直接展示给用户的中文错误。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004111')

    response = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'json', 'content': '{bad-json'}, headers=_auth_header(member['access_token']))

    assert response.status_code == 400
    assert response.json() == {'detail': '无法解析 JSON 内容'}


def test_running_data_import_wizard_rejects_csv_without_header(tmp_path: Path) -> None:
    """没有 CSV 表头时向导应返回 400。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004112')

    response = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'csv', 'content': '\n\n'}, headers=_auth_header(member['access_token']))

    assert response.status_code == 400
    assert response.json() == {'detail': '无法解析 CSV 表头'}


def test_running_data_import_wizard_uses_preview_limit_for_long_files(tmp_path: Path) -> None:
    """长文件只返回前 20 行预览。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004113')
    rows = '\n'.join(f'活动{i},2026-06-01T07:{i:02d}:00,{5 + i / 10},{1800 + i}' for i in range(25))

    response = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'csv', 'content': f'活动名称,开始时间,距离(km),用时(秒)\n{rows}\n'}, headers=_auth_header(member['access_token']))

    assert response.status_code == 200
    assert len(response.json()['data']['preview']) == 20


def test_running_data_import_wizard_rejects_csv_with_too_many_rows(tmp_path: Path) -> None:
    """CSV 超过最大行数时返回 413。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004114')
    rows = '\n'.join(f'活动{i},2026-06-01T07:{i:02d}:00,{5 + i / 10},{1800 + i}' for i in range(1001))

    response = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'csv', 'content': f'活动名称,开始时间,距离(km),用时(秒)\n{rows}\n'}, headers=_auth_header(member['access_token']))

    assert response.status_code == 413
    assert response.json() == {'detail': '导入行数超过限制'}


def test_running_data_import_wizard_rejects_csv_with_too_many_columns(tmp_path: Path) -> None:
    """CSV 列数超过上限时返回 413。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004115')
    headers = ['活动名称'] + [f'扩展{i}' for i in range(41)]
    row = ['晨跑'] + ['x' for _ in range(41)]
    content = ','.join(headers) + '\n' + ','.join(row) + '\n'

    response = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'csv', 'content': content}, headers=_auth_header(member['access_token']))

    assert response.status_code == 413
    assert response.json() == {'detail': '导入字段数量超过限制'}


def test_running_data_import_wizard_rejects_sensitive_csv_headers(tmp_path: Path) -> None:
    """CSV 出现敏感表头时返回 422。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004116')

    response = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'generic', 'format': 'csv', 'content': 'title,access_token,start_time,distance_km,duration_seconds\n晨跑,secret,2026-06-01T07:00:00,5,1800\n'},
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 422
    assert '导入文件包含敏感字段' in response.json()['detail']
    assert 'access_token' in response.json()['detail']


def test_running_data_import_wizard_rejects_sensitive_json_keys(tmp_path: Path) -> None:
    """JSON 出现敏感键时返回 422。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004117')

    response = client.post(
        '/api/v1/running-data-imports/wizard',
        json={
            'source': 'generic',
            'format': 'json',
            'content': '[{"name":"晨跑","start_time":"2026-06-01T07:00:00","distance_km":5,"duration_seconds":1800,"secret":"abc"}]',
        },
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 422
    assert '导入文件包含敏感字段' in response.json()['detail']
    assert 'secret' in response.json()['detail']


def test_running_data_import_wizard_rejects_json_with_too_many_rows(tmp_path: Path) -> None:
    """JSON 超过最大行数时返回 413。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004118')
    items = ','.join(
        f'{{"name":"活动{i}","start_time":"2026-06-01T07:{i:02d}:00","distance_km":5,"duration_seconds":1800}}'
        for i in range(1001)
    )

    response = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'json', 'content': f'[{items}]'}, headers=_auth_header(member['access_token']))

    assert response.status_code == 413
    assert response.json() == {'detail': '导入行数超过限制'}
