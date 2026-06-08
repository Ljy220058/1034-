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
    assert payload['save_location']['table'] == 'running_import_consents'
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


def test_running_data_import_start_writes_consent_record(tmp_path: Path) -> None:
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
    payload = response.json()['data']
    assert payload['status'] == 'authorized_precheck_only'
    assert payload['source']['id'] == 'manual_file'
    assert payload['import_started'] is False
    assert payload['authorized_scope']['precheck_id'] == 'running-data-imports:manual_file:v1'
    assert payload['authorized_scope']['scope_version'] == 'running-data-imports.v1'
    assert payload['consent_record']['member_id'] == member['member']['id']
    assert payload['consent_record']['source'] == 'manual_file'
    assert payload['consent_record']['revoked_at'] is None
    assert payload['consent_record']['read_fields'] == [
        'activity_id',
        'distance_meters',
        'duration_seconds',
        'gps_track_summary',
        'heart_rate_summary',
        'pace_seconds_per_km',
        'started_at',
    ]
    assert payload['next_step'] == 'frontend may request the real importer after showing the precheck panel'

    with database.connect() as connection:
        row = connection.execute(
            'SELECT member_id, source, read_fields, consent_version, granted_at, revoked_at FROM running_import_consents WHERE member_id = ? AND source = ? ORDER BY id DESC LIMIT 1',
            (member['member']['id'], 'manual_file'),
        ).fetchone()
    assert row is not None
    assert row['member_id'] == member['member']['id']
    assert row['source'] == 'manual_file'
    assert row['revoked_at'] is None


def test_running_data_import_start_requires_active_consent(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client)

    response = client.post(
        '/api/v1/running-data-imports/start',
        json={
            'source': 'garmin',
            'consent_acknowledged': True,
            'precheck_id': 'running-data-imports:garmin:v1',
            'scope_version': 'running-data-imports.v1',
        },
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 403
    assert response.json() == {'detail': '该数据源尚未完成有效授权或授权已撤销'}


def test_running_data_import_consent_can_be_revoked_and_then_blocks_import(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client)

    start_response = client.post(
        '/api/v1/running-data-imports/start',
        json={
            'source': 'coros',
            'consent_acknowledged': True,
            'precheck_id': 'running-data-imports:coros:v1',
            'scope_version': 'running-data-imports.v1',
        },
        headers=_auth_header(member['access_token']),
    )
    assert start_response.status_code == 202

    revoke_response = client.delete(
        '/api/v1/running-data-imports/consent',
        params={'source': 'coros'},
        headers=_auth_header(member['access_token']),
    )
    assert revoke_response.status_code == 200
    revoke_payload = revoke_response.json()['data']['consent']
    assert revoke_payload['source'] == 'coros'
    assert revoke_payload['revoked_at'] is not None

    retry_response = client.post(
        '/api/v1/running-data-imports/start',
        json={
            'source': 'coros',
            'consent_acknowledged': True,
            'precheck_id': 'running-data-imports:coros:v1',
            'scope_version': 'running-data-imports.v1',
        },
        headers=_auth_header(member['access_token']),
    )
    assert retry_response.status_code == 403
    assert retry_response.json() == {'detail': '该数据源尚未完成有效授权或授权已撤销'}


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
