from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.routes.common import token_for_member
from backend.repository import get_member, update_member


def _client(tmp_path: Path) -> TestClient:
    """创建使用临时 SQLite 的测试客户端。"""
    database.init_db(tmp_path / 'test.db')
    return TestClient(app, raise_server_exceptions=False)


def _auth_header(token: str) -> dict[str, str]:
    """构造 Bearer 认证头。"""
    return {'Authorization': f'Bearer {token}'}


def _register_member(client: TestClient, *, phone: str, role: str = 'member') -> dict[str, Any]:
    """注册测试成员并返回响应 data。"""
    response = client.post(
        '/api/v1/auth/register',
        json={'name': '认证测试员', 'phone': phone, 'password': 'secret123', 'role': role},
    )
    assert response.status_code == 201
    return response.json()['data']


def _unsigned_token(member_id: int, role: str) -> str:
    """构造未签名旧格式 token。"""
    return f'{member_id}:{role}:2099-01-01T00:00:00+00:00'


def _tampered_exp_token(token: str) -> str:
    """篡改 JWT 载荷中的 exp 且保留原签名。"""
    header, payload, signature = token.split('.')
    padded = payload + '=' * (-len(payload) % 4)
    data = json.loads(base64.urlsafe_b64decode(padded.encode('ascii')))
    data['exp'] = int(time.time()) + 60 * 60 * 24 * 30
    encoded = base64.urlsafe_b64encode(
        json.dumps(data, separators=(',', ':')).encode('utf-8')
    ).decode('ascii').rstrip('=')
    return f'{header}.{encoded}.{signature}'


def test_running_data_import_wizard_rejects_unsigned_forged_token(tmp_path: Path) -> None:
    """导入向导拒绝未签名旧格式伪造 token。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900008801')
    forged = _unsigned_token(member['member']['id'], member['member']['role'])

    response = client.post(
        '/api/v1/running-data-imports/wizard',
        json={
            'source': 'generic',
            'format': 'csv',
            'content': '活动名称,开始时间,距离(km),用时(秒)\n晨跑,2026-06-01T07:00:00,5,1800\n',
        },
        headers=_auth_header(forged),
    )

    assert response.status_code == 401
    assert response.json() == {'detail': '未授权或 token 已过期'}


def test_running_data_import_wizard_rejects_expired_token(tmp_path: Path) -> None:
    """导入向导拒绝 exp 已过期的 JWT。"""
    client = _client(tmp_path)
    member_data = _register_member(client, phone='13900008802')
    member = get_member(member_data['member']['id'])
    assert member is not None
    expired_token = token_for_member(member, expires_in_seconds=-60)

    response = client.post(
        '/api/v1/running-data-imports/wizard',
        json={
            'source': 'generic',
            'format': 'csv',
            'content': '活动名称,开始时间,距离(km),用时(秒)\n晨跑,2026-06-01T07:00:00,5,1800\n',
        },
        headers=_auth_header(expired_token),
    )

    assert response.status_code == 401
    assert response.json() == {'detail': '未授权或 token 已过期'}


def test_running_data_import_wizard_accepts_signed_token(tmp_path: Path) -> None:
    """导入向导接受合法签名 JWT 并返回标准响应。"""
    client = _client(tmp_path)
    member = _register_member(client, phone='13900008803')

    response = client.post(
        '/api/v1/running-data-imports/wizard',
        json={
            'source': 'generic',
            'format': 'csv',
            'content': '活动名称,开始时间,距离(km),用时(秒)\n晨跑,2026-06-01T07:00:00,5,1800\n',
        },
        headers=_auth_header(member['access_token']),
    )

    assert response.status_code == 200
    assert response.json()['message'] == '成功'
    assert response.json()['data']['current_user_id'] == member['member']['id']


def test_signed_token_rejects_tampered_exp_and_role_change(tmp_path: Path) -> None:
    """JWT 篡改 exp 或成员角色变更后都应被拒绝。"""
    client = _client(tmp_path)
    member_data = _register_member(client, phone='13900008804')
    member = get_member(member_data['member']['id'])
    assert member is not None
    expired_token = token_for_member(member, expires_in_seconds=-60)
    tampered = _tampered_exp_token(expired_token)

    tampered_response = client.post(
        '/api/v1/running-data-imports/wizard',
        json={
            'source': 'generic',
            'format': 'csv',
            'content': '活动名称,开始时间,距离(km),用时(秒)\n晨跑,2026-06-01T07:00:00,5,1800\n',
        },
        headers=_auth_header(tampered),
    )
    assert tampered_response.status_code == 401
    assert tampered_response.json() == {'detail': '未授权或 token 已过期'}

    updated = update_member(member.id, {'role': 'leader'})
    assert updated is not None
    old_role_response = client.post(
        '/api/v1/running-data-imports/wizard',
        json={
            'source': 'generic',
            'format': 'csv',
            'content': '活动名称,开始时间,距离(km),用时(秒)\n晨跑,2026-06-01T07:00:00,5,1800\n',
        },
        headers=_auth_header(member_data['access_token']),
    )
    assert old_role_response.status_code == 401
    assert old_role_response.json() == {'detail': '未授权或 token 已过期'}
