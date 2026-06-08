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


def _register_admin(client: TestClient) -> dict[str, Any]:
    response = client.post(
        '/api/v1/auth/register',
        json={'name': 'Import Admin', 'phone': '13900007777', 'password': 'secret123', 'role': 'admin'},
    )
    assert response.status_code == 201
    return response.json()['data']


def test_running_data_import_anomaly_precheck_rejects_sensitive_csv_headers(tmp_path: Path) -> None:
    """CSV 导入遇到敏感表头时应返回 422 中文错误。"""
    client = _client(tmp_path)
    admin = _register_admin(client)

    response = client.post(
        '/api/v1/running-data-imports/anomaly-precheck',
        json={
            'source': 'generic',
            'format': 'csv',
            'content': 'title,password,start_time,duration_seconds,distance_meters,gps_track\n晨跑,123,2026-06-06 07:00:00,1800,5000,track_a',
        },
        headers=_auth_header(admin['access_token']),
    )

    assert response.status_code == 422
    assert response.json() == {'detail': '导入文件包含敏感字段：password'}


def test_running_data_import_anomaly_precheck_rejects_sensitive_json_keys(tmp_path: Path) -> None:
    """JSON 导入遇到敏感字段时应返回 422 中文错误。"""
    client = _client(tmp_path)
    admin = _register_admin(client)

    response = client.post(
        '/api/v1/running-data-imports/anomaly-precheck',
        json={
            'source': 'generic',
            'format': 'json',
            'content': '[{"name": "晨跑", "startTime": "2026-06-06T07:00:00", "duration": 1800, "distance": 5, "token": "abc"}]',
        },
        headers=_auth_header(admin['access_token']),
    )

    assert response.status_code == 422
    assert response.json() == {'detail': '第 1 项包含敏感字段：token'}


def test_running_data_import_anomaly_precheck_rejects_csv_over_row_limit(tmp_path: Path) -> None:
    """CSV 行数超过上限时应返回 413 中文错误。"""
    client = _client(tmp_path)
    admin = _register_admin(client)
    rows = ['title,start_time,duration_seconds,distance_meters,gps_track']
    for index in range(201):
        rows.append(f'晨跑{index},2026-06-06 07:00:00,1800,5000,track_{index}')

    response = client.post(
        '/api/v1/running-data-imports/anomaly-precheck',
        json={'source': 'generic', 'format': 'csv', 'content': '\n'.join(rows)},
        headers=_auth_header(admin['access_token']),
    )

    assert response.status_code == 413
    assert response.json() == {'detail': '导入行数超过限制'}


def test_running_data_import_anomaly_precheck_rejects_csv_over_column_limit(tmp_path: Path) -> None:
    """CSV 列数超过上限时应返回 413 中文错误。"""
    client = _client(tmp_path)
    admin = _register_admin(client)
    headers = [f'col{i}' for i in range(41)]
    values = [str(i) for i in range(41)]

    response = client.post(
        '/api/v1/running-data-imports/anomaly-precheck',
        json={
            'source': 'generic',
            'format': 'csv',
            'content': ','.join(headers) + '\n' + ','.join(values),
        },
        headers=_auth_header(admin['access_token']),
    )

    assert response.status_code == 413
    assert response.json() == {'detail': '导入字段数量超过限制'}


def test_running_data_import_anomaly_precheck_rejects_json_over_row_limit(tmp_path: Path) -> None:
    """JSON 数组行数超过上限时应返回 413 中文错误。"""
    client = _client(tmp_path)
    admin = _register_admin(client)
    items = []
    for index in range(201):
        items.append({'name': f'晨跑{index}', 'startTime': '2026-06-06T07:00:00', 'duration': 1800, 'distance': 5})

    response = client.post(
        '/api/v1/running-data-imports/anomaly-precheck',
        json={'source': 'generic', 'format': 'json', 'content': __import__('json').dumps(items)},
        headers=_auth_header(admin['access_token']),
    )

    assert response.status_code == 413
    assert response.json() == {'detail': '导入行数超过限制'}


def test_running_data_import_anomaly_precheck_rejects_json_over_column_limit(tmp_path: Path) -> None:
    """JSON 对象字段数超过上限时应返回 413 中文错误。"""
    client = _client(tmp_path)
    admin = _register_admin(client)
    payload = {'name': '晨跑', 'startTime': '2026-06-06T07:00:00', 'duration': 1800, 'distance': 5}
    for index in range(37):
        payload[f'extra_{index}'] = index

    response = client.post(
        '/api/v1/running-data-imports/anomaly-precheck',
        json={'source': 'generic', 'format': 'json', 'content': __import__('json').dumps([payload])},
        headers=_auth_header(admin['access_token']),
    )

    assert response.status_code == 413
    assert response.json() == {'detail': '第 1 项字段数量超过限制'}


def test_running_data_import_anomaly_precheck_accepts_safe_csv_and_reports_anomalies(tmp_path: Path) -> None:
    """安全 CSV 应可通过，且返回结构化异常清单。"""
    client = _client(tmp_path)
    admin = _register_admin(client)
    content = (
        'title,start_time,duration_seconds,distance_meters,gps_track\n'
        '缺时间,,1800,5000,track_a\n'
        '正常跑,2026-06-06 07:00:00,1800,5000,track_b\n'
        '正常跑,2026-06-06 07:00:00,1800,5000,track_b\n'
    )

    response = client.post(
        '/api/v1/running-data-imports/anomaly-precheck',
        json={'source': 'generic', 'format': 'csv', 'content': content},
        headers=_auth_header(admin['access_token']),
    )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '成功'
    data = body['data']
    assert data['source'] == {'id': 'generic', 'name': '通用'}
    assert data['count'] == 3
    assert data['anomalies']['summary']['can_import'] is False
    assert data['anomalies']['summary']['severity_count']['high'] >= 1
    assert any(item['code'] == '字段缺失' for item in data['anomalies']['anomalies'])
    assert data['sample_response']['message'] == '预检完成'
