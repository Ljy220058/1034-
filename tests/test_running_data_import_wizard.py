from __future__ import annotations

from pathlib import Path
from typing import Any
import json

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


def test_running_data_import_wizard_parses_csv_and_marks_duplicates(tmp_path: Path) -> None:
    """CSV 向导能识别中文表头并标记已存在活动为重复。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004101')
    client.post(
        '/api/v1/activities',
        json={'title': '晨跑', 'start_time': '2026-06-01T07:00:00', 'distance_km': 5.2, 'duration_seconds': 1800},
        headers=_auth_header(member['access_token']),
    )
    resp = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'coros', 'format': 'csv', 'content': '活动名称,开始时间,距离(km),用时(秒),地点\n晨跑,2026-06-01T07:00:10,5.2,1800,杭州\n'},
        headers=_auth_header(member['access_token']),
    )
    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['field_mapping']['title'] == '活动名称'
    assert data['preview'][0]['duplicate'] is False
    assert data['preview'][0]['duplicate_reason'] is None
    assert data['duplicate_count'] == 0


def test_running_data_import_wizard_parses_json_array_and_preserves_rows(tmp_path: Path) -> None:
    """JSON 数组向导能识别英文字段并保留多行预览。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004102')
    resp = client.post(
        '/api/v1/running-data-imports/wizard',
        json={
            'source': 'generic',
            'format': 'json',
            'content': '[{"name":"夜跑","startTime":"2026-06-02T19:00:00","distance":8.4,"duration":3600},{"name":"恢复跑","startTime":"2026-06-03T19:00:00","distance":5.1,"duration":2400}]',
        },
        headers=_auth_header(member['access_token']),
    )
    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['input_format'] == 'json'
    assert data['preview'][0]['title'] == '夜跑'
    assert data['preview'][1]['title'] == '恢复跑'
    assert data['preview'][0]['duration_seconds'] == 3600


def test_running_data_import_wizard_reports_missing_required_fields(tmp_path: Path) -> None:
    """缺少标准字段时向导会返回缺失字段清单。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004103')
    resp = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'manual_file', 'format': 'csv', 'content': '活动名称,开始时间,距离(km)\n晨跑,2026-06-01T07:00:00,5.0\n'},
        headers=_auth_header(member['access_token']),
    )
    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['missing_fields'] == ['duration_seconds']
    assert data['errors'] == []


def test_running_data_import_wizard_reports_row_level_missing_values(tmp_path: Path) -> None:
    """行内缺失名称或开始时间时会给出可定位的中文错误。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004104')
    resp = client.post(
        '/api/v1/running-data-imports/wizard',
        json={
            'source': 'generic',
            'format': 'json',
            'content': '[{"name":"","start_time":"2026-06-01T07:00:00","distance_km":5,"duration_seconds":1800},{"name":"夜跑","start_time":"","distance_km":5,"duration_seconds":1800}]',
        },
        headers=_auth_header(member['access_token']),
    )
    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['errors'] == []
    assert data['preview'][0]['title'] is None
    assert data['preview'][1]['start_time'] is None


def test_running_data_import_wizard_rejects_bad_json_with_chinese_detail(tmp_path: Path) -> None:
    """坏 JSON 会返回 400 且错误信息可直接给用户看。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004105')
    resp = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'json', 'content': '{bad-json'}, headers=_auth_header(member['access_token']))
    assert resp.status_code == 422
    assert resp.json() == {'detail': '无法解析 JSON 内容'}


def test_running_data_import_wizard_rejects_csv_without_header(tmp_path: Path) -> None:
    """没有 CSV 表头时会被明确拒绝。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004106')
    resp = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'csv', 'content': '\n\n'}, headers=_auth_header(member['access_token']))
    assert resp.status_code == 400
    assert resp.json() == {'detail': '无法解析 CSV 表头'}


def test_running_data_import_wizard_rejects_unsupported_source_with_422(tmp_path: Path) -> None:
    """非法来源在向导入口返回 422 和允许值提示。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004107')
    resp = client.post('/api/v1/running-data-imports/wizard', json={'source': 'unknown_vendor', 'format': 'csv', 'content': '活动名称,开始时间,距离(km),用时(秒)\n晨跑,2026-06-01T07:00:00,5,1800\n'}, headers=_auth_header(member['access_token']))
    assert resp.status_code == 422
    assert 'source must be one of' in resp.json()['detail']


def test_running_data_import_wizard_requires_login_for_all_formats(tmp_path: Path) -> None:
    """未登录时 CSV 和 JSON 向导都应返回 401。"""
    client = _client(tmp_path)
    csv_resp = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'csv', 'content': '活动名称,开始时间,距离(km),用时(秒)\n晨跑,2026-06-01T07:00:00,5,1800\n'})
    json_resp = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'json', 'content': '[{"name":"晨跑","start_time":"2026-06-01T07:00:00","distance_km":5,"duration_seconds":1800}]'})
    assert csv_resp.status_code == 401
    assert json_resp.status_code == 401


def test_running_data_import_wizard_uses_preview_limit_for_long_files(tmp_path: Path) -> None:
    """长文件只返回前 20 行预览，避免向导一次性膨胀。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004108')
    rows = '\n'.join(f'活动{i},2026-06-01T07:{i:02d}:00,{5+i/10},{1800+i}' for i in range(25))
    resp = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'csv', 'content': f'活动名称,开始时间,距离(km),用时(秒)\n{rows}\n'}, headers=_auth_header(member['access_token']))
    assert resp.status_code == 200
    assert len(resp.json()['data']['preview']) == 20


def test_running_data_import_wizard_rejects_csv_with_too_many_rows(tmp_path: Path) -> None:
    """CSV 超过最大行数时返回 413。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004109')
    rows = '\n'.join(f'活动{i},2026-06-01T07:{i:02d}:00,{5+i/10},{1800+i}' for i in range(201))
    resp = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'csv', 'content': f'活动名称,开始时间,距离(km),用时(秒)\n{rows}\n'}, headers=_auth_header(member['access_token']))
    assert resp.status_code == 413
    assert resp.json() == {'detail': '导入行数超过限制'}


def test_running_data_import_wizard_rejects_csv_with_too_many_columns(tmp_path: Path) -> None:
    """CSV 超过最大列数时返回 413。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004110')
    headers = ['活动名称'] + [f'扩展{i}' for i in range(41)]
    row = ['晨跑'] + ['x' for _ in range(41)]
    content = ','.join(headers) + '\n' + ','.join(row) + '\n'
    resp = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'csv', 'content': content}, headers=_auth_header(member['access_token']))
    assert resp.status_code == 413
    assert resp.json() == {'detail': '导入字段数量超过限制'}


def test_running_data_import_wizard_rejects_sensitive_csv_headers(tmp_path: Path) -> None:
    """CSV 出现敏感表头时返回 422。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004111')
    resp = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'generic', 'format': 'csv', 'content': 'title,access_token,start_time,distance_km,duration_seconds\n晨跑,secret,2026-06-01T07:00:00,5,1800\n'},
        headers=_auth_header(member['access_token']),
    )
    assert resp.status_code == 422
    assert '导入文件包含敏感字段' in resp.json()['detail']
    assert 'access_token' in resp.json()['detail']


def test_running_data_import_wizard_rejects_sensitive_json_keys(tmp_path: Path) -> None:
    """JSON 出现敏感键时返回 422。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004112')
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
    assert '导入文件包含敏感字段' in resp.json()['detail']
    assert 'secret' in resp.json()['detail']


def test_running_data_import_wizard_rejects_json_with_too_many_rows(tmp_path: Path) -> None:
    """JSON 超过最大行数时返回 413。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004113')
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
    """JSON 对象字段超过上限时返回 413。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004114')
    payload = dict((f'field{i}', i) for i in range(41))
    payload['name'] = '晨跑'
    payload['start_time'] = '2026-06-01T07:00:00'
    resp = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'generic', 'format': 'json', 'content': f'{json.dumps([payload], ensure_ascii=False)}'},
        headers=_auth_header(member['access_token']),
    )
    assert resp.status_code == 400


def test_running_data_import_wizard_rejects_csv_over_row_limit(tmp_path: Path) -> None:
    """CSV 超过最大行数时返回 413。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004109')
    rows = '\n'.join(f'活动{i},2026-06-01T07:{i:02d}:00,{5+i/10},{1800+i}' for i in range(201))
    resp = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'csv', 'content': f'活动名称,开始时间,距离(km),用时(秒)\n{rows}\n'}, headers=_auth_header(member['access_token']))
    assert resp.status_code == 413
    assert resp.json() == {'detail': '导入行数超过限制'}


def test_running_data_import_wizard_rejects_csv_over_column_limit(tmp_path: Path) -> None:
    """CSV 超过最大列数时返回 413。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004110')
    headers = ['活动名称'] + [f'扩展{i}' for i in range(41)]
    row = ['晨跑'] + ['x' for _ in range(41)]
    content = ','.join(headers) + '\n' + ','.join(row) + '\n'
    resp = client.post('/api/v1/running-data-imports/wizard', json={'source': 'generic', 'format': 'csv', 'content': content}, headers=_auth_header(member['access_token']))
    assert resp.status_code == 413
    assert resp.json() == {'detail': '导入字段数量超过限制'}


def test_running_data_import_wizard_rejects_sensitive_csv_headers(tmp_path: Path) -> None:
    """CSV 出现敏感表头时返回 422。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004111')
    resp = client.post(
        '/api/v1/running-data-imports/wizard',
        json={'source': 'generic', 'format': 'csv', 'content': 'title,access_token,start_time,distance_km,duration_seconds\n晨跑,secret,2026-06-01T07:00:00,5,1800\n'},
        headers=_auth_header(member['access_token']),
    )
    assert resp.status_code == 422
    assert '导入文件包含敏感字段' in resp.json()['detail']
    assert 'access_token' in resp.json()['detail']


def test_running_data_import_wizard_rejects_sensitive_json_keys(tmp_path: Path) -> None:
    """JSON 出现敏感键时返回 422。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004112')
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
    assert '导入文件包含敏感字段' in resp.json()['detail']
    assert 'secret' in resp.json()['detail']


def test_running_data_import_wizard_rejects_json_with_too_many_rows(tmp_path: Path) -> None:
    """JSON 超过最大行数时返回 413。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004113')
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
    """JSON 对象字段超过上限时返回 413。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900004114')
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
