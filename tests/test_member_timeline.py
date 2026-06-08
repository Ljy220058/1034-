from __future__ import annotations

import sqlite3

import backend.database as database_module
from backend.app import app
from backend.database import init_db


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


def test_member_stats_summary_returns_api_response(tmp_path, monkeypatch):
    db_path = tmp_path / 'member_timeline.db'
    monkeypatch.setattr(database_module, 'DB_PATH', db_path)
    init_db(db_path)
    _seed_member_timeline(db_path)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get('/api/v1/members/1/stats-summary')

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == ''
    data = payload['data']
    assert data['member_id'] == 1
    assert data['total_activities'] == 5
    assert data['total_distance_km'] == 46.0
    assert data['current_streak_days'] == 0
    assert data['best_streak_days'] == 1
    assert data['best_month'] == '2025-01'


def test_member_timeline_groups_by_month(tmp_path, monkeypatch):
    db_path = tmp_path / 'member_timeline.db'
    monkeypatch.setattr(database_module, 'DB_PATH', db_path)
    init_db(db_path)
    _seed_member_timeline(db_path)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get('/api/v1/members/1/timeline?year=2025')

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == ''
    assert payload['data'] == [
        {
            'month': '2025-01',
            'activities': [
                {
                    'date': '2025-01-05',
                    'activity_id': 1,
                    'title': '一月晨跑',
                    'distance_km': 8.0,
                    'pace_min_per_km': None,
                    'photo_thumbnail': '/photos/1-thumb.jpg',
                },
                {
                    'date': '2025-01-20',
                    'activity_id': 2,
                    'title': '一月夜跑',
                    'distance_km': 10.5,
                    'pace_min_per_km': None,
                    'photo_thumbnail': '/photos/2.jpg',
                },
            ],
        },
        {
            'month': '2025-02',
            'activities': [
                {
                    'date': '2025-02-08',
                    'activity_id': 3,
                    'title': '二月拉练',
                    'distance_km': 12.0,
                    'pace_min_per_km': None,
                    'photo_thumbnail': '',
                },
                {
                    'date': '2025-02-22',
                    'activity_id': 4,
                    'title': '二月节奏跑',
                    'distance_km': 6.5,
                    'pace_min_per_km': None,
                    'photo_thumbnail': '/photos/4-thumb.jpg',
                },
            ],
        },
    ]


def test_member_timeline_missing_member_returns_not_found(tmp_path, monkeypatch):
    db_path = tmp_path / 'member_timeline_missing.db'
    monkeypatch.setattr(database_module, 'DB_PATH', db_path)
    init_db(db_path)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get('/api/v1/members/999/stats-summary')

    assert response.status_code == 404
    assert response.json() == {'detail': '成员不存在'}
