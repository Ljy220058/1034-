from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.passwords import hash_password
from backend.repository import create_member, reset_database
from backend.routes.common import token_for_member


class _AuthMember:
    def __init__(self, member_id: int, role: str) -> None:
        self.id = member_id
        self.role = role


def _client(tmp_path: Path) -> TestClient:
    database.init_db(tmp_path / 'test.db')
    client = TestClient(app)
    with client:
        pass
    return client


def _auth_headers(role: str, phone: str) -> dict[str, str]:
    member_id = create_member(
        name=f'Test{role.title()}',
        phone=phone,
        role=role,
        running_years=1,
        pace='5:00',
        usual_distance_km=10,
        training_goal='5k',
        password_hash=hash_password('secret123'),
    )
    token = token_for_member(_AuthMember(member_id, role))
    return {'Authorization': f'Bearer {token}'}


def test_running_data_import_consent_归一化字段并去重保存(tmp_path: Path) -> None:
    """授权接口会清洗字段并去重后保存。"""
    client = _client(tmp_path)
    headers = _auth_headers('member', '13900005101')

    response = client.post(
        '/api/v1/running-data-imports/consent',
        json={'source': '  GARMIN  ', 'read_fields': [' pace_seconds_per_km ', 'pace_seconds_per_km', 'gps_track_summary', ' '], 'consent_version': ' v1 '},
        headers=headers,
    )

    assert response.status_code == 201
    consent = response.json()['data']['consent']
    assert consent['source'] == 'garmin'
    assert consent['read_fields'] == ['gps_track_summary', 'pace_seconds_per_km']


def test_running_data_import_consent_缺少读取字段_返回422(tmp_path: Path) -> None:
    """read_fields 为空时返回 422。"""
    client = _client(tmp_path)
    headers = _auth_headers('member', '13900005102')

    response = client.post(
        '/api/v1/running-data-imports/consent',
        json={'source': 'garmin', 'read_fields': [], 'consent_version': 'v1'},
        headers=headers,
    )

    assert response.status_code == 422
    assert 'read_fields cannot be empty' in str(response.json()['detail'])


def test_running_data_import_consent_无认证_返回401(tmp_path: Path) -> None:
    """授权接口在未登录时返回 401。"""
    client = _client(tmp_path)

    response = client.post(
        '/api/v1/running-data-imports/consent',
        json={'source': 'garmin', 'read_fields': ['gps_track_summary'], 'consent_version': 'v1'},
    )

    assert response.status_code == 401


def test_running_data_import_consent_敏感字段_返回422(tmp_path: Path) -> None:
    """授权接口会拒绝敏感字段组合。"""
    client = _client(tmp_path)
    headers = _auth_headers('member', '13900005103')

    response = client.post(
        '/api/v1/running-data-imports/consent',
        json={'source': 'garmin', 'read_fields': ['access_token', ' gps_track_summary '], 'consent_version': 'v1'},
        headers=headers,
    )

    assert response.status_code == 422
    assert 'access_token' in response.json()['detail']


def test_running_data_import_wizard_csv_敏感表头_返回422(tmp_path: Path) -> None:
    """CSV 向导会拒绝包含敏感表头的内容。"""
    client = _client(tmp_path)
    headers = _auth_headers('member', '13900005104')

    response = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'manual_file', 'format': 'csv', 'content': 'title,password\n晨跑,123456'},
        headers=headers,
    )

    assert response.status_code == 422
    assert 'password' in response.json()['detail']


def test_running_data_import_wizard_json_缺少名称_返回错误列表(tmp_path: Path) -> None:
    """JSON 向导会把缺少名称的记录标记为错误。"""
    client = _client(tmp_path)
    headers = _auth_headers('member', '13900005105')

    response = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'manual_file', 'format': 'json', 'content': '[{"start_time":"2026-06-09T07:00:00","distance_km":5.2}]'},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()['data']['errors'] == [{'field': 'title', 'message': '缺少必填字段', 'row': 1}]
