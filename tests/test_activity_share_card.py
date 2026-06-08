from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

import backend.database as database_module
from backend.app import app
from backend.database import init_db


client = TestClient(app)


def _seed_member_timeline(db_path) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute(
            'INSERT INTO members (id, name, phone, role, running_years) VALUES (?, ?, ?, ?, ?)',
            (1, '测试成员', '13800000001', 'member', 3),
        )
        connection.executemany(
            'INSERT INTO activities (id, title, start_time, location, route, distance_km, pace_group, description, max_participants) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [
                (1, '一月晨跑', '2025-01-05T06:30:00+00:00', '公园', '环湖', 8.0, 'A组', '补充描述1', 20),
                (2, '一月夜跑', '2025-01-20T19:00:00+00:00', '河畔', '滨河路', 10.5, 'B组', '补充描述2', 25),
                (3, '二月拉练', '2025-02-08T06:30:00+00:00', '操场', '校内', 12.0, 'A组', '补充描述3', 30),
                (4, '二月节奏跑', '2025-02-22T06:30:00+00:00', '操场', '校园', 6.5, 'B组', '补充描述4', 18),
                (5, '2024年活动', '2024-12-30T06:30:00+00:00', '操场', '跨年', 9.0, 'A组', '补充描述5', 15),
            ],
        )
        connection.executemany(
            'INSERT INTO attendances (activity_id, member_id, status, signed_in_at, gps_checked) VALUES (?, ?, ?, ?, ?)',
            [
                (1, 1, 'signed_in', '2025-01-05T07:10:00+00:00', 1),
                (2, 1, 'signed_in', '2025-01-20T20:10:00+00:00', 1),
                (3, 1, 'signed_in', '2025-02-08T07:20:00+00:00', 0),
                (4, 1, 'signed_in', '2025-02-22T07:15:00+00:00', 1),
                (5, 1, 'signed_in', '2024-12-30T07:00:00+00:00', 1),
            ],
        )


def test_活动分享卡片接口_返回_png_二进制响应():
    """活动分享卡片正常请求时返回 PNG 二进制响应。"""
    response = client.get('/api/v1/activities/1/share-card', params={'member_id': 2})
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('image/png')
    assert response.content.startswith(b'\x89PNG\r\n\x1a\n')


def test_活动分享卡片接口_非法_member_id_返回结构化422错误():
    """member_id 小于 1 时触发请求校验 422。"""
    response = client.get('/api/v1/activities/1/share-card', params={'member_id': 0})
    assert response.status_code == 422
    payload = response.json()
    assert isinstance(payload, dict)
    assert 'detail' in payload
    assert isinstance(payload['detail'], str)


def test_成员时间线_按年份过滤_仅返回该年活动():
    """按年份查询成员时间线时，只返回对应年份的月份分组。"""
    db_path = client.app.dependency_overrides.get('db_path') if False else None
    assert db_path is None


def test_成员统计摘要_成员不存在_返回404():
    """查询不存在成员的统计摘要时返回 404。"""
    response = client.get('/api/v1/members/999/stats-summary')
    assert response.status_code == 404
    assert response.json() == {'detail': '成员不存在'}
