from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.database import connect, init_db
from tests.conftest import make_auth_headers


@pytest.fixture()
def temp_db(monkeypatch, tmp_path: Path):
    """为每个测试创建独立临时数据库。"""
    db_path = tmp_path / 'test.db'
    monkeypatch.setenv('RUNNING_CLUB_DB_PATH', str(db_path))
    init_db(db_path)
    return db_path


@pytest.fixture()
def client(temp_db):
    """使用临时数据库的 FastAPI 测试客户端。"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def member_headers(client):
    """创建普通成员认证头。"""
    return make_auth_headers(client, '13800000001', role='member')


@pytest.fixture()
def admin_headers(client):
    """创建管理员认证头。"""
    return make_auth_headers(client, '13800000002', role='admin')


@pytest.fixture()
def leader_headers(client):
    """创建队长认证头。"""
    return make_auth_headers(client, '13800000003', role='leader')


@pytest.fixture()
def seeded_member_id(temp_db):
    """插入一个可用于成员读写的普通成员。"""
    with connect(temp_db) as connection:
        cursor = connection.execute(
            """
            INSERT INTO members (name, phone, role, running_years, pace, usual_distance_km, training_goal, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ('Seed Member', '13800000011', 'member', 2, '5:30', 10.0, 'keep running', 'hash'),
        )
    return cursor.lastrowid


@pytest.fixture()
def seeded_admin_member_id(temp_db):
    """插入一个可用于权限校验的管理员成员。"""
    with connect(temp_db) as connection:
        cursor = connection.execute(
            """
            INSERT INTO members (name, phone, role, running_years, pace, usual_distance_km, training_goal, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ('Seed Admin', '13800000012', 'admin', 3, '5:10', 12.0, 'train harder', 'hash'),
        )
    return cursor.lastrowid


@pytest.fixture()
def seeded_leader_member_id(temp_db):
    """插入一个可用于权限校验的队长成员。"""
    with connect(temp_db) as connection:
        cursor = connection.execute(
            """
            INSERT INTO members (name, phone, role, running_years, pace, usual_distance_km, training_goal, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ('Seed Leader', '13800000013', 'leader', 4, '4:50', 15.0, 'lead team', 'hash'),
        )
    return cursor.lastrowid


@pytest.fixture()
def sample_activity(temp_db):
    """插入一条活动数据供成员接口关联使用。"""
    with connect(temp_db) as connection:
        cursor = connection.execute(
            """
            INSERT INTO activities (title, start_time, location, route, distance_km, pace_group, description, max_participants)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ('Sunday Run', '2026-06-09T07:00:00+00:00', 'Central Park', 'Loop', 5.0, '5:30', 'Weekly run', 20),
        )
    return cursor.lastrowid


def test_auth_register_成功返回成员和令牌(client):
    """首次注册成功时返回 201、访问令牌和公开成员信息。"""
    resp = client.post('/api/v1/auth/register', json={'name': 'Alice', 'phone': '13810000001', 'password': 'secret123'})
    assert resp.status_code == 201
    assert resp.json()['data']['member']['phone'] == '13810000001'


def test_auth_register_缺少必填字段返回422(client):
    """缺少注册必填字段时返回 422。"""
    resp = client.post('/api/v1/auth/register', json={'name': 'Alice'})
    assert resp.status_code == 422


def test_auth_register_重复手机号返回409(client):
    """同一手机号重复注册时返回 409 冲突。"""
    payload = {'name': 'Alice', 'phone': '13810000002', 'password': 'secret123'}
    client.post('/api/v1/auth/register', json=payload)
    resp = client.post('/api/v1/auth/register', json=payload)
    assert resp.status_code == 409


def test_auth_register_已存在成员后尝试提权返回403(client):
    """已有成员后注册 admin 身份会被拒绝。"""
    client.post('/api/v1/auth/register', json={'name': 'Alice', 'phone': '13810000003', 'password': 'secret123'})
    resp = client.post('/api/v1/auth/register', json={'name': 'Bob', 'phone': '13810000004', 'password': 'secret123', 'role': 'admin'})
    assert resp.status_code == 403


def test_auth_login_密码正确返回200(client):
    """已注册成员使用正确密码登录时返回 200。"""
    client.post('/api/v1/auth/register', json={'name': 'Alice', 'phone': '13810000005', 'password': 'secret123'})
    resp = client.post('/api/v1/auth/login', json={'phone': '13810000005', 'password': 'secret123'})
    assert resp.status_code == 200


def test_auth_login_手机号不存在返回401(client):
    """不存在的手机号登录时返回 401。"""
    resp = client.post('/api/v1/auth/login', json={'phone': '13810000006', 'password': 'secret123'})
    assert resp.status_code == 401


def test_members_me_未认证返回401(client):
    """未携带 token 访问 /me 时返回 401。"""
    resp = client.get('/api/v1/members/me')
    assert resp.status_code == 401


def test_members_me_认证后返回当前成员(member_headers, client):
    """携带有效 token 访问 /me 时返回当前成员信息。"""
    resp = client.get('/api/v1/members/me', headers=member_headers)
    assert resp.status_code == 200


def test_members_list_普通成员访问返回403(member_headers, client):
    """普通成员无权查看成员列表。"""
    resp = client.get('/api/v1/members', headers=member_headers)
    assert resp.status_code == 403


def test_members_list_管理员访问返回200(admin_headers, client):
    """管理员可以查看成员列表。"""
    resp = client.get('/api/v1/members', headers=admin_headers)
    assert resp.status_code == 200


def test_members_read_未认证返回401(client, seeded_member_id):
    """未登录时读取成员详情返回 401。"""
    resp = client.get(f'/api/v1/members/{seeded_member_id}')
    assert resp.status_code == 401


def test_members_read_普通成员读取他人返回403(client, member_headers, seeded_member_id):
    """普通成员读取他人详情时返回 403。"""
    resp = client.get(f'/api/v1/members/{seeded_member_id}', headers=member_headers)
    assert resp.status_code == 403


def test_members_read_管理员读取成员返回200(client, admin_headers, seeded_member_id):
    """管理员读取成员详情时返回 200。"""
    resp = client.get(f'/api/v1/members/{seeded_member_id}', headers=admin_headers)
    assert resp.status_code == 200


def test_members_update_缺少必填字段返回422(client, admin_headers, seeded_member_id):
    """PATCH 会员时空 body 会触发 422。"""
    resp = client.patch(f'/api/v1/members/{seeded_member_id}', headers=admin_headers, json={})
    assert resp.status_code == 422


def test_members_update_普通成员修改他人返回403(client, member_headers, seeded_member_id):
    """普通成员不能修改他人资料。"""
    resp = client.patch(f'/api/v1/members/{seeded_member_id}', headers=member_headers, json={'name': 'New Name'})
    assert resp.status_code == 403


def test_members_update_管理员修改成员返回200(client, admin_headers, seeded_member_id):
    """管理员可以修改成员资料。"""
    resp = client.patch(f'/api/v1/members/{seeded_member_id}', headers=admin_headers, json={'name': 'Updated Name'})
    assert resp.status_code == 200


def test_members_delete_普通成员删除成员返回403(client, member_headers, seeded_member_id):
    """普通成员不能删除成员。"""
    resp = client.delete(f'/api/v1/members/{seeded_member_id}', headers=member_headers)
    assert resp.status_code == 403


def test_members_delete_管理员删除普通成员返回200(client, admin_headers, seeded_member_id):
    """管理员删除普通成员时返回 200。"""
    resp = client.delete(f'/api/v1/members/{seeded_member_id}', headers=admin_headers)
    assert resp.status_code == 200
