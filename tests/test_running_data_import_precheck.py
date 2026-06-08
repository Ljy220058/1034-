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
    payload = response.json()['data']
    assert payload['source']['id'] == 'garmin'
    assert payload['authorization_required'] is True
    assert payload['can_start_import'] is False
    assert payload['consent_required'] is True
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
    assert payload['revocation']['endpoint'] == '/api/v1/running-data-imports/consent'
    assert payload['revocation']['method'] == 'DELETE'
    assert '高驰' in payload['privacy_boundary']['supported_sources']
    assert payload['privacy_boundary']['third_party_credentials'] == 'never_store_password_or_raw_token'
    assert payload['authorization_fields'] == [
        {'key': 'source', 'label': '数据来源', 'value': '佳明', 'required': True},
        {'key': 'read_fields', 'label': '将读取的字段', 'value': payload['read_fields'], 'required': True},
        {'key': 'save_location', 'label': '保存位置', 'value': payload['save_location'], 'required': True},
        {'key': 'revocation', 'label': '撤销方式', 'value': payload['revocation'], 'required': True},
        {'key': 'failure_handling', 'label': '失败处理', 'value': payload['failure_handling'], 'required': True},
        {'key': 'privacy_boundary', 'label': '隐私边界', 'value': payload['privacy_boundary'], 'required': True},
    ]
    assert payload['consent_artifact'] == {
        'precheck_id': 'running-data-imports:garmin:v1',
        'scope_version': 'running-data-imports.v1',
        'required_acknowledgement': '我已阅读并同意本次跑步数据导入授权范围',
    }
    assert '失败时不写入活动记录' in payload['failure_handling']['import_failure']


def test_running_data_import_precheck_rejects_unsupported_source(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client)

    response = client.get(
        '/api/v1/running-data-imports/precheck',
        params={'source': 'unknown_vendor'},
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 422
    detail = response.json()['detail']
    assert 'source must be one of' in str(detail)


def test_running_data_import_start_requires_explicit_consent(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client)

    response = client.post(
        '/api/v1/running-data-imports/start',
        json={'source': 'manual_file', 'consent_acknowledged': False},
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 403
    assert response.json()['detail'] == '跑步数据导入需要先确认授权范围'


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
    assert response.json()['detail'] == '跑步数据导入需要匹配的预检确认记录'


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
    payload = response.json()['data']
    assert payload['status'] == 'authorized_precheck_only'
    assert payload['source']['id'] == 'manual_file'
    assert payload['import_started'] is False
    assert payload['authorized_scope']['precheck_id'] == 'running-data-imports:manual_file:v1'
    assert payload['authorized_scope']['scope_version'] == 'running-data-imports.v1'
    assert payload['next_step'] == 'frontend may request the real importer after showing the precheck panel'


def test_running_data_import_endpoints_reject_missing_auth(tmp_path: Path) -> None:
    client = _client(tmp_path)

    precheck = client.get('/api/v1/running-data-imports/precheck', params={'source': 'garmin'})
    start = client.post('/api/v1/running-data-imports/start', json={'source': 'garmin', 'consent_acknowledged': True})

    assert precheck.status_code == 401
    assert start.status_code == 401


def test_running_data_import_precheck_returns_structured_consent_and_scope_metadata(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client)

    response = client.get(
        '/api/v1/running-data-imports/precheck',
        params={'source': 'coros'},
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '预检完成'
    data = body['data']
    assert data['source'] == {'id': 'coros', 'name': '高驰'}
    assert data['consent_artifact'] == {
        'precheck_id': 'running-data-imports:coros:v1',
        'scope_version': 'running-data-imports.v1',
        'required_acknowledgement': '我已阅读并同意本次跑步数据导入授权范围',
    }
    assert data['save_location']['record_scope'] == 'current_user_only'
    assert data['revocation'] == {'endpoint': '/api/v1/running-data-imports/consent', 'method': 'DELETE'}
    assert data['authorization_required'] is True
    assert data['can_start_import'] is False


def test_running_data_import_start_rejects_scope_mismatch_and_uses_safe_error_detail(tmp_path: Path) -> None:
    client = _client(tmp_path)
    member = _register_member(client)

    response = client.post(
        '/api/v1/running-data-imports/start',
        json={
            'source': 'coros',
            'consent_acknowledged': True,
            'precheck_id': 'running-data-imports:coros:v1',
            'scope_version': 'running-data-imports.v2',
        },
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 403
    assert response.json() == {'detail': '跑步数据导入需要匹配的授权范围版本'}
