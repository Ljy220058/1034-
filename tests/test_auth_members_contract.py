from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend import database as db
from backend.database import init_db
from conftest import make_auth_headers


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """使用独立临时数据库的测试客户端。"""
    db_path = tmp_path / 'auth_members.db'
    db.DB_PATH = db_path
    init_db(db_path)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def member_headers(client: TestClient) -> dict[str, str]:
    """创建普通成员认证头。"""
    return make_auth_headers(client, '13820000001', role='member')


@pytest.fixture()
def admin_headers(client: TestClient) -> dict[str, str]:
    """创建管理员认证头。"""
    return make_auth_headers(client, '13820000002', role='admin')


@pytest.fixture()
def leader_headers(client: TestClient) -> dict[str, str]:
    """创建队长认证头。"""
    return make_auth_headers(client, '13820000003', role='leader')


@pytest.fixture()
def seeded_member_id(tmp_path: Path) -> int:
    """插入一个普通成员，供读写与权限测试使用。"""
    from backend.database import connect

    db_path = tmp_path / 'auth_members.db'
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO members (name, phone, role, running_years, pace, usual_distance_km, training_goal, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ('Seed Member', '13820000011', 'member', 2, '5:30', 10.0, 'keep running', 'hash'),
        )
    return cursor.lastrowid


def test_auth_register_成功返回令牌和成员信息(client: TestClient) -> None:
    """首次注册成功时返回 201 和公开成员信息。"""
    response = client.post('/api/v1/auth/register', json={'name': 'Alice', 'phone': '13821000001', 'password': 'secret123'})
    assert response.status_code == 201
    assert response.json()['data']['member']['phone'] == '13821000001'


def test_auth_register_缺少必填字段返回422(client: TestClient) -> None:
    """注册缺少字段时返回 422。"""
    response = client.post('/api/v1/auth/register', json={'name': 'Alice'})
    assert response.status_code == 422


def test_auth_register_重复手机号返回409(client: TestClient) -> None:
    """同一手机号重复注册会返回 409。"""
    payload = {'name': 'Alice', 'phone': '13821000002', 'password': 'secret123'}
    client.post('/api/v1/auth/register', json=payload)
    response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 409


def test_auth_login_密码正确返回200(client: TestClient) -> None:
    """已注册成员使用正确密码登录时返回 200。"""
    client.post('/api/v1/auth/register', json={'name': 'Alice', 'phone': '13821000003', 'password': 'secret123'})
    response = client.post('/api/v1/auth/login', json={'phone': '13821000003', 'password': 'secret123'})
    assert response.status_code == 200


def test_auth_login_手机号不存在返回401(client: TestClient) -> None:
    """不存在的手机号登录时返回 401。"""
    response = client.post('/api/v1/auth/login', json={'phone': '13821000004', 'password': 'secret123'})
    assert response.status_code == 401


def test_members_me_未认证返回401(client: TestClient) -> None:
    """未携带 token 访问 /me 时返回 401。"""
    response = client.get('/api/v1/members/me')
    assert response.status_code == 401


def test_members_me_认证后返回当前成员(client: TestClient, member_headers: dict[str, str]) -> None:
    """携带有效 token 访问 /me 时返回当前成员。"""
    response = client.get('/api/v1/members/me', headers=member_headers)
    assert response.status_code == 200


def test_members_list_普通成员访问返回403(client: TestClient, member_headers: dict[str, str]) -> None:
    """普通成员无权查看成员列表。"""
    response = client.get('/api/v1/members', headers=member_headers)
    assert response.status_code == 403


def test_members_list_管理员访问返回200(client: TestClient, admin_headers: dict[str, str]) -> None:
    """管理员可以查看成员列表。"""
    response = client.get('/api/v1/members', headers=admin_headers)
    assert response.status_code == 200


def test_members_read_未认证返回401(client: TestClient, seeded_member_id: int) -> None:
    """未登录时读取成员详情返回 401。"""
    response = client.get(f'/api/v1/members/{seeded_member_id}')
    assert response.status_code == 401


def test_members_read_普通成员读取他人返回403(client: TestClient, member_headers: dict[str, str], seeded_member_id: int) -> None:
    """普通成员读取他人详情时返回 403。"""
    response = client.get(f'/api/v1/members/{seeded_member_id}', headers=member_headers)
    assert response.status_code == 403


def test_members_read_管理员读取成员返回200(client: TestClient, admin_headers: dict[str, str], seeded_member_id: int) -> None:
    """管理员读取成员详情时返回 200。"""
    response = client.get(f'/api/v1/members/{seeded_member_id}', headers=admin_headers)
    assert response.status_code == 200


def test_members_read_不存在成员返回404(client: TestClient, admin_headers: dict[str, str]) -> None:
    """读取不存在成员时返回 404。"""
    response = client.get('/api/v1/members/999999', headers=admin_headers)
    assert response.status_code == 404


def test_members_update_缺少必填字段返回422(client: TestClient, admin_headers: dict[str, str], seeded_member_id: int) -> None:
    """PATCH 会员时空 body 会触发 422。"""
    response = client.patch(f'/api/v1/members/{seeded_member_id}', headers=admin_headers, json={})
    assert response.status_code == 422


def test_members_update_普通成员修改他人返回403(client: TestClient, member_headers: dict[str, str], seeded_member_id: int) -> None:
    """普通成员不能修改他人资料。"""
    response = client.patch(f'/api/v1/members/{seeded_member_id}', headers=member_headers, json={'name': 'New Name'})
    assert response.status_code == 403


def test_members_update_管理员修改成员返回200(client: TestClient, admin_headers: dict[str, str], seeded_member_id: int) -> None:
    """管理员可以修改成员资料。"""
    response = client.patch(f'/api/v1/members/{seeded_member_id}', headers=admin_headers, json={'name': 'Updated Name'})
    assert response.status_code == 200


def test_members_delete_普通成员删除成员返回403(client: TestClient, member_headers: dict[str, str], seeded_member_id: int) -> None:
    """普通成员不能删除成员。"""
    response = client.delete(f'/api/v1/members/{seeded_member_id}', headers=member_headers)
    assert response.status_code == 403


def test_members_delete_管理员删除普通成员返回200(client: TestClient, admin_headers: dict[str, str], seeded_member_id: int) -> None:
    """管理员删除普通成员时返回 200。"""
    response = client.delete(f'/api/v1/members/{seeded_member_id}', headers=admin_headers)
    assert response.status_code == 200
