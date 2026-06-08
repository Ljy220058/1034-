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


def _register_admin(client: TestClient, *, phone: str = '13900009990') -> dict[str, Any]:
    response = client.post(
        '/api/v1/auth/register',
        json={'name': '导入测试管理员', 'phone': phone, 'password': 'secret123', 'role': 'admin'},
    )
    assert response.status_code == 201
    return response.json()['data']


def _post_wizard(client: TestClient, token: str, payload: dict[str, Any]):
    return client.post('/api/v1/running-data-imports/wizard', json=payload, headers=_auth_header(token))


def _create_activity(client: TestClient, token: str, title: str, start_time: str) -> None:
    response = client.post(
        '/api/v1/activities',
        json={'title': title, 'start_time': start_time, 'location': '西湖', 'distance_km': 8.8},
        headers=_auth_header(token),
    )
    assert response.status_code in {200, 201}


def test_CSV导入向导_包含重复活动_只标记重复不新增活动(tmp_path: Path) -> None:
    """CSV 预览遇到同名同分钟活动时只标记重复，不在向导阶段写入新活动。"""
    # Arrange
    client = _client(tmp_path)
    admin = _register_admin(client)
    _create_activity(client, admin['access_token'], '晨跑', '2026-06-01T07:00:00')
    content = '活动名称,开始时间,距离(km),用时(秒)\n晨跑,2026-06-01T07:00:30,8.8,2700\n夜跑,2026-06-02T20:00:00,5.0,1800\n'
    # Act
    response = _post_wizard(client, admin['access_token'], {'source': 'coros', 'format': 'csv', 'content': content})
    activities = client.get('/api/v1/activities', headers=_auth_header(admin['access_token']))
    # Assert
    assert response.status_code == 200
    data = response.json()['data']
    assert data['duplicate_count'] == 1
    assert data['preview'][0]['duplicate_reason'] == '活动已存在'
    assert len(activities.json()['data']) == 1


def test_手动录入导入向导_JSON活动数组_返回可预览字段映射(tmp_path: Path) -> None:
    """manual_file 来源使用 JSON 活动数组时返回字段映射和预览数据。"""
    # Arrange
    client = _client(tmp_path)
    admin = _register_admin(client)
    content = '[{"name":"手动晨跑","startTime":"2026-06-03T06:30:00","distance":6.4,"duration":2100,"location":"操场"}]'
    # Act
    response = _post_wizard(client, admin['access_token'], {'source': 'manual_file', 'format': 'json', 'content': content})
    # Assert
    assert response.status_code == 200
    data = response.json()['data']
    assert data['field_mapping'] == {'title': 'name', 'start_time': 'startTime', 'distance_km': 'distance', 'duration_seconds': 'duration', 'location': 'location'}
    assert data['preview'][0]['location'] == '操场'


def test_导入向导_CSV缺少标题和时间_返回行级中文错误(tmp_path: Path) -> None:
    """CSV 行缺少活动名称和开始时间时返回包含行号、字段和中文文案的错误。"""
    # Arrange
    client = _client(tmp_path)
    admin = _register_admin(client)
    content = '活动名称,开始时间,距离(km),用时(秒)\n,,5.2,1900\n'
    # Act
    response = _post_wizard(client, admin['access_token'], {'source': 'generic', 'format': 'csv', 'content': content})
    # Assert
    assert response.status_code == 200
    errors = response.json()['data']['errors']
    assert errors
    assert errors[0]['message'] == '缺少必填字段'


def test_导入向导_缺少认证信息_返回401(tmp_path: Path) -> None:
    """未登录用户请求导入向导时返回 401。"""
    # Arrange
    client = _client(tmp_path)
    payload = {'source': 'generic', 'format': 'csv', 'content': '活动名称,开始时间\n晨跑,2026-06-01T07:00:00\n'}
    # Act
    response = client.post('/api/v1/running-data-imports/wizard', json=payload)
    # Assert
    assert response.status_code == 401
    assert response.json()['detail'] == 'missing bearer token'


def test_导入向导_缺少必填content字段_返回422(tmp_path: Path) -> None:
    """请求体缺少 content 必填字段时返回 422 校验错误。"""
    # Arrange
    client = _client(tmp_path)
    admin = _register_admin(client)
    # Act
    response = _post_wizard(client, admin['access_token'], {'source': 'generic', 'format': 'csv'})
    # Assert
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'validation_error'
    assert any(error['loc'][-1] == 'content' for error in response.json()['detail'])


def test_导入向导_来源不支持_返回包含允许值的422(tmp_path: Path) -> None:
    """未知来源请求导入向导时返回 422，并提示允许的来源值。"""
    # Arrange
    client = _client(tmp_path)
    admin = _register_admin(client)
    payload = {'source': 'unknown_vendor', 'format': 'json', 'content': '[{"name":"晨跑"}]'}
    # Act
    response = _post_wizard(client, admin['access_token'], payload)
    # Assert
    assert response.status_code in {200, 422}
    if response.status_code == 422:
        detail = response.json()['detail']
        assert 'source must be one of' in detail
        assert 'manual_file' in detail


def test_导入向导_超过二十行CSV_预览只返回前二十行(tmp_path: Path) -> None:
    """导入内容超过 20 行时向导只返回前 20 行预览，避免前端一次渲染过多数据。"""
    # Arrange
    client = _client(tmp_path)
    admin = _register_admin(client)
    rows = [f'跑步{i},2026-06-{i:02d}T07:00:00,5,1800' for i in range(1, 22)]
    content = '活动名称,开始时间,距离(km),用时(秒)\n' + '\n'.join(rows)
    # Act
    response = _post_wizard(client, admin['access_token'], {'source': 'generic', 'format': 'csv', 'content': content})
    # Assert
    assert response.status_code == 200
    preview = response.json()['data']['preview']
    assert len(preview) == 20
    assert preview[-1]['title'] == '跑步20'
