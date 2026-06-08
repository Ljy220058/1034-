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


def _register_member(client: TestClient, *, phone: str = '13900003001') -> dict[str, Any]:
    response = client.post(
        '/api/v1/auth/register',
        json={'name': 'Privacy Runner', 'phone': phone, 'password': 'secret123', 'role': 'member'},
    )
    assert response.status_code == 201
    return response.json()['data']


def _register_leader(client: TestClient, *, phone: str = '13900003999') -> dict[str, Any]:
    response = client.post(
        '/api/v1/auth/register',
        json={'name': 'Privacy Leader', 'phone': phone, 'password': 'secret123', 'role': 'leader'},
    )
    assert response.status_code == 201
    return response.json()['data']


def test_running_data_import_precheck_discloses_authorization_scope(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client)

    response = client.get(
        '/api/v1/running-data-imports/precheck',
        params={'source': 'garmin'},
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '预检完成'
    payload = body['data']
    assert payload['source']['id'] == 'garmin'
    assert payload['authorization_required'] is True
    assert payload['can_start_import'] is False
    assert payload['consent_required'] is True
    assert payload['current_user_id'] == member['member']['id']
    assert payload['read_fields'] == [
        'activity_id',
        'started_at',
        'duration_seconds',
        'distance_meters',
        'pace_seconds_per_km',
        'heart_rate_summary',
        'gps_track_summary',
    ]
    assert payload['save_location']['table'] == 'running_data_imports'
    assert payload['save_location']['record_scope'] == 'current_user_only'
    assert payload['failure_handling']['import_failure'] == '失败时不写入活动记录，保留授权确认但不继续导入'
    assert payload['privacy_boundary']['third_party_credentials'] == 'never_store_password_or_raw_token'
    assert payload['consent_artifact'] == {
        'precheck_id': 'running-data-imports:garmin:v1',
        'scope_version': 'running-data-imports.v1',
        'required_acknowledgement': '我已阅读并同意本次跑步数据导入授权范围',
    }


def test_running_data_import_precheck_rejects_unsupported_source(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client)

    response = client.get(
        '/api/v1/running-data-imports/precheck',
        params={'source': 'unknown_vendor'},
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 422
    assert 'source must be one of' in str(response.json()['detail'])


def test_running_data_import_start_requires_explicit_consent(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client)

    response = client.post(
        '/api/v1/running-data-imports/start',
        json={'source': 'manual_file', 'consent_acknowledged': False},
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 403
    assert response.json() == {'detail': '跑步数据导入需要先确认授权范围'}


def test_running_data_import_start_requires_matching_precheck_artifact(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client)

    response = client.post(
        '/api/v1/running-data-imports/start',
        json={
            'source': 'garmin',
            'consent_acknowledged': True,
            'precheck_id': 'running-data-imports:coros:v1',
            'scope_version': 'running-data-imports.v1',
        },
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 403
    assert response.json() == {'detail': '跑步数据导入需要匹配的预检确认记录'}


def test_running_data_import_start_requires_matching_scope_version(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client)

    response = client.post(
        '/api/v1/running-data-imports/start',
        json={
            'source': 'garmin',
            'consent_acknowledged': True,
            'precheck_id': 'running-data-imports:garmin:v1',
            'scope_version': 'running-data-imports.v2',
        },
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 403
    assert response.json() == {'detail': '跑步数据导入需要匹配的授权范围版本'}


def test_running_data_import_start_returns_safe_dry_run_when_authorized(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client)

    response = client.post(
        '/api/v1/running-data-imports/start',
        json={
            'source': 'manual_file',
            'consent_acknowledged': True,
            'precheck_id': 'running-data-imports:manual_file:v1',
            'scope_version': 'running-data-imports.v1',
        },
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 202
    body = response.json()
    assert body['message'] == '成功'
    payload = body['data']
    assert payload['status'] == 'authorized_precheck_only'
    assert payload['source']['id'] == 'manual_file'
    assert payload['import_started'] is False
    assert payload['authorized_scope'] == {
        'current_user_id': member['member']['id'],
        'source': 'manual_file',
        'precheck_id': 'running-data-imports:manual_file:v1',
        'consent_version': 'running-data-imports.v1',
        'scope': 'running-data-imports:manual_file:scope',
    }
    assert payload['next_step'] == 'frontend may request the real importer after showing the precheck panel'


def test_running_data_import_endpoints_reject_missing_auth(tmp_path: Path) -> None:
    client = _client(tmp_path)

    precheck = client.get('/api/v1/running-data-imports/precheck', params={'source': 'garmin'})
    start = client.post('/api/v1/running-data-imports/start', json={'source': 'garmin', 'consent_acknowledged': True})

    assert precheck.status_code == 401
    assert start.status_code == 401


def test_running_data_import_wizard_returns_preview_and_missing_fields(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004101')

    response = client.post(
        '/api/v1/running-data-imports/wizard',
        json={
            'source': 'generic',
            'format': 'csv',
            'content': '活动名称,开始时间,距离(km),用时(秒),地点\n晨跑,2026-06-01T07:00:10,5.2,1800,杭州\n',
        },
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '成功'
    data = body['data']
    assert data['input_format'] == 'csv'
    assert data['field_mapping']['title'] == '活动名称'
    assert data['missing_fields'] == []
    assert data['preview'][0]['title'] == '晨跑'
    assert data['preview'][0]['distance_km'] == 5.2
    assert data['current_user_id'] == member['member']['id']


def test_running_data_import_wizard_reports_missing_required_fields(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004103')
    response = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'manual_file', 'format': 'csv', 'content': '活动名称,开始时间,距离(km)\n晨跑,2026-06-01T07:00:00,5.0\n'},
        headers=_auth_header(member['access_token']),
    )
    assert response.status_code == 200
    data = response.json()['data']
    assert data['missing_fields'] == ['duration_seconds']
    assert data['errors'] == []


def test_running_data_import_wizard_parses_json_array_and_preserves_rows(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004102')
    resp = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'generic', 'format': 'json', 'content': '[{"name":"夜跑","startTime":"2026-06-02T19:00:00","distance":8.4,"duration":3600},{"name":"恢复跑","startTime":"2026-06-03T19:00:00","distance":5.1,"duration":2400}]'},
        headers=_auth_header(member['access_token']),
    )
    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['input_format'] == 'json'
    assert data['preview'][0]['title'] == '夜跑'
    assert data['preview'][1]['title'] == '恢复跑'
    assert data['preview'][0]['duration_seconds'] == 3600


def test_running_data_import_wizard_reports_row_level_missing_values(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004104')
    resp = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'json', 'content': '[{"name":"","start_time":"2026-06-01T07:00:00","distance_km":5,"duration_seconds":1800},{"name":"夜跑","start_time":"","distance_km":5,"duration_seconds":1800}]'}, headers=_auth_header(member['access_token']))
    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['preview'][0]['title'] is None
    assert data['preview'][1]['start_time'] is None


def test_running_data_import_wizard_rejects_bad_json_with_chinese_detail(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004105')
    resp = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'json', 'content': '{bad-json'}, headers=_auth_header(member['access_token']))
    assert resp.status_code == 400
    assert resp.json() == {'detail': '无法解析 JSON 内容'}


def test_running_data_import_wizard_rejects_csv_without_header(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004106')
    resp = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'csv', 'content': '\n\n'}, headers=_auth_header(member['access_token']))
    assert resp.status_code == 422
    assert resp.json() == {'detail': '无法解析 CSV 表头'}


def test_running_data_import_wizard_rejects_unsupported_source_with_422(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004107')
    resp = client.post('/api/v1/running-data-imports/wizard', json={'source': 'unknown_vendor', 'format': 'csv', 'content': 'a,b\n1,2'}, headers=_auth_header(member['access_token']))
    assert resp.status_code == 422
    assert 'source must be one of' in str(resp.json()['detail'])


def test_running_data_import_wizard_rejects_sensitive_headers(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004108')
    resp = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'generic', 'format': 'csv', 'content': 'title,password\n晨跑,abc'},
        headers=_auth_header(member['access_token']),
    )
    assert resp.status_code == 422
    assert resp.json() == {'detail': '导入文件包含敏感字段：password'}


def test_running_data_import_wizard_rejects_csv_with_too_many_rows(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004115')
    rows = '\n'.join(f'活动{i},2026-06-01T07:{i:02d}:00,{5+i/10},{1800+i}' for i in range(201))
    resp = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'generic', 'format': 'csv', 'content': f'活动名称,开始时间,距离(km),用时(秒)\n{rows}\n'},
        headers=_auth_header(member['access_token']),
    )
    assert resp.status_code == 413
    assert resp.json() == {'detail': '导入行数超过限制'}


def test_running_data_import_wizard_rejects_csv_with_too_many_columns(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004116')
    headers = ['活动名称'] + [f'扩展{i}' for i in range(41)]
    row = ['晨跑'] + ['x' for _ in range(41)]
    content = ','.join(headers) + '\n' + ','.join(row) + '\n'
    resp = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'generic', 'format': 'csv', 'content': content},
        headers=_auth_header(member['access_token']),
    )
    assert resp.status_code == 413
    assert resp.json() == {'detail': '导入字段数量超过限制'}


def test_running_data_import_wizard_rejects_csv_row_with_too_many_columns(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004117')
    content = '活动名称,开始时间\n晨跑,2026-06-01T07:00:00,extra\n'
    resp = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'generic', 'format': 'csv', 'content': content},
        headers=_auth_header(member['access_token']),
    )
    assert resp.status_code == 413
    assert resp.json() == {'detail': '第 2 行列数超过表头限制'}


def test_running_data_import_wizard_rejects_json_with_too_many_rows(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004118')
    items = ','.join(
        f'{{"name":"活动{i}","start_time":"2026-06-01T07:{i:02d}:00","distance_km":5,"duration_seconds":1800}}'
        for i in range(201)
    )
    resp = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'generic', 'format': 'json', 'content': f'[{items}]'},
        headers=_auth_header(member['access_token']),
    )
    assert resp.status_code == 413
    assert resp.json() == {'detail': '导入行数超过限制'}


def test_running_data_import_wizard_rejects_json_with_too_many_fields(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004119')
    payload = dict((f'field{i}', i) for i in range(41))
    payload['name'] = '晨跑'
    payload['start_time'] = '2026-06-01T07:00:00'
    resp = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'generic', 'format': 'json', 'content': f'{json.dumps([payload], ensure_ascii=False)}'},
        headers=_auth_header(member['access_token']),
    )
    assert resp.status_code == 413
    assert resp.json() == {'detail': '第 1 项字段数量超过限制'}


def test_running_data_import_wizard_rejects_sensitive_json_keys(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004120')
    resp = client.post(
        '/api/v1/running-data-imports/wizard',
        json={
            'source': 'generic',
            'format': 'json',
            'content': '[{"name":"晨跑","start_time":"2026-06-01T07:00:00","distance_km":5,"duration_seconds":1800,"secret":"abc"}]',
        },
        headers=_auth_header(member['access_token']),
    )
    assert resp.status_code == 422
    assert resp.json() == {'detail': '导入文件包含敏感字段：secret'}


def test_running_data_import_wizard_rejects_other_users_private_activity_in_precheck(tmp_path: Path) -> None:
    client = _client(tmp_path)
    actor = _register_member(client, phone='13900004203')
    leader = _register_leader(client, phone='13900004204')

    leader_activity = client.post(
        '/api/v1/activities',
        json={
            'title': 'Private Leader Route',
            'start_time': '2026-06-06T07:00:00',
            'distance_km': 8.0,
            'duration_minutes': 50,
            'max_participants': 12,
        },
        headers=_auth_header(leader['access_token']),
    )
    assert leader_activity.status_code == 201

    response = client.get(
        '/api/v1/running-data-imports/precheck',
        params={'source': 'garmin'},
        headers=_auth_header(actor['access_token']),
    )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '预检完成'
    assert body['data']['current_user_id'] == actor['member']['id']
    assert body['data']['source']['id'] == 'garmin'
