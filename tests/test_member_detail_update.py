from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from backend.app import app
from backend.passwords import hash_password
from backend.repository import create_member, reset_database
from backend.routes.common import token_for_member


@dataclass(frozen=True)
class _AuthMember:
    id: int
    role: str


def _client() -> TestClient:
    reset_database()
    return TestClient(app)


def _headers(role: str, phone: str) -> dict[str, str]:
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
    token = token_for_member(_AuthMember(id=member_id, role=role))
    return {'Authorization': f'Bearer {token}'}


def test_读取成员详情_管理员访问他人_返回200() -> None:
    """管理员读取他人详情时返回 200。"""
    client = _client()
    headers = _headers('admin', '13000001001')
    target_id = create_member('目标成员', '13000001002', 'member', 1, '5:30', 10, '5k', hash_password('secret123'))

    resp = client.get(f'/api/v1/members/{target_id}', headers=headers)

    assert resp.status_code == 200
    assert resp.json()['data']['phone'] == '13000001002'


def test_读取成员详情_缺少token_返回401() -> None:
    """未登录访问成员详情时返回 401。"""
    client = _client()
    target_id = create_member('目标成员', '13000001003', 'member', 1, '5:30', 10, '5k', hash_password('secret123'))

    resp = client.get(f'/api/v1/members/{target_id}')

    assert resp.status_code == 401


def test_读取成员详情_普通成员访问他人_返回403() -> None:
    """普通成员读取他人详情时返回 403。"""
    client = _client()
    headers = _headers('member', '13000001004')
    target_id = create_member('目标成员', '13000001005', 'member', 1, '5:30', 10, '5k', hash_password('secret123'))

    resp = client.get(f'/api/v1/members/{target_id}', headers=headers)

    assert resp.status_code == 403


def test_更新成员_缺少必填字段_返回422() -> None:
    """PATCH 空载荷时触发请求校验错误。"""
    client = _client()
    headers = _headers('admin', '13000001006')
    target_id = create_member('目标成员', '13000001007', 'member', 1, '5:30', 10, '5k', hash_password('secret123'))

    resp = client.patch(f'/api/v1/members/{target_id}', headers=headers, json={})

    assert resp.status_code == 422


def test_更新成员_管理员修改成功_返回200() -> None:
    """管理员修改成员信息时返回 200。"""
    client = _client()
    headers = _headers('admin', '13000001008')
    target_id = create_member('目标成员', '13000001009', 'member', 1, '5:30', 10, '5k', hash_password('secret123'))

    resp = client.patch(f'/api/v1/members/{target_id}', headers=headers, json={'name': '新名字'})

    assert resp.status_code == 200
    assert resp.json()['data']['name'] == '新名字'
