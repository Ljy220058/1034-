from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from backend.app import app
from backend.passwords import hash_password
from backend.repository import create_member, get_member, reset_database
from backend.routes.common import token_for_member


@dataclass(frozen=True)
class _AuthMember:
    id: int
    role: str


def _client() -> TestClient:
    reset_database()
    return TestClient(app)


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
    member = get_member(member_id)
    token = token_for_member(_AuthMember(id=member.id, role=member.role))
    return {'Authorization': f'Bearer {token}'}


def test_获取成员列表_管理员已认证_返回200():
    """管理员携带有效 token 时可以读取成员列表。"""
    client = _client()
    headers = _auth_headers('admin', '13000000001')

    resp = client.get('/api/v1/members', headers=headers)

    assert resp.status_code == 200
    assert isinstance(resp.json()['data'], list)


def test_获取成员列表_缺少token_返回401():
    """未携带认证信息访问成员列表会被拒绝。"""
    client = _client()

    resp = client.get('/api/v1/members')

    assert resp.status_code == 401
    assert '未授权' in resp.json()['detail'] or 'missing bearer token' in resp.json()['detail']


def test_获取成员列表_普通成员访问_返回403():
    """普通成员不能读取全量成员列表。"""
    client = _client()
    headers = _auth_headers('member', '13000000002')

    resp = client.get('/api/v1/members', headers=headers)

    assert resp.status_code == 403


def test_创建成员_字段缺失_返回422():
    """缺少必填字段时创建成员会触发请求校验错误。"""
    client = _client()
    headers = _auth_headers('admin', '13000000003')

    resp = client.post('/api/v1/members', headers=headers, json={'phone': '13000000007'})

    assert resp.status_code == 422


def test_创建成员_管理员提交合法载荷_返回201():
    """管理员提交完整成员信息时可以成功创建成员。"""
    client = _client()
    headers = _auth_headers('admin', '13000000004')

    resp = client.post('/api/v1/members', headers=headers, json={'name': '新成员', 'phone': '13000000005', 'role': 'member'})

    assert resp.status_code == 201
    assert resp.json()['data']['phone'] == '13000000005'


def test_修改成员_普通成员越权修改他人_返回403():
    """普通成员不能修改其他成员的信息。"""
    client = _client()
    headers = make_auth_headers(client, '13000000006', role='member')

    resp = client.patch('/api/v1/members/999', headers=headers, json={'name': '被拒绝'})

    assert resp.status_code == 403
