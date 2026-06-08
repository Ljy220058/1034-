from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

import backend.database as database_module
from backend.app import app
from backend.database import init_db


def _seed_member_and_attendances(db_path, member_id: int = 1):
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute(
            'INSERT INTO members (id, name, phone, role, running_years) VALUES (?, ?, ?, ?, ?)',
            (member_id, '测试成员', f'138000000{member_id:02d}', 'member', 3),
        )
        connection.executemany(
            'INSERT INTO activities (id, title, start_time, location, distance_km) VALUES (?, ?, ?, ?, ?)',
            [
                (1, '周末晨跑', '2026-06-01T06:30:00+00:00', '公园', 8.0),
                (2, '周中晨跑', '2026-06-08T06:30:00+00:00', '公园', 8.0),
                (3, '周中夜跑', '2026-06-06T06:30:00+00:00', '公园', 8.0),
                (4, '去年的晨跑', '2025-07-01T06:30:00+00:00', '公园', 8.0),
                (5, '更早的晨跑', '2025-06-01T06:30:00+00:00', '公园', 8.0),
                (6, '缺席活动', '2026-06-10T06:30:00+00:00', '公园', 8.0),
            ],
        )
        rows = [
            (1, 1, member_id, 'signed_in', '2026-06-09T06:30:00+00:00', 1),
            (2, 2, member_id, 'signed_in', '2026-06-08T06:30:00+00:00', 1),
            (3, 3, member_id, 'signed_in', '2026-06-06T06:30:00+00:00', 1),
            (4, 4, member_id, 'signed_in', '2025-07-01T06:30:00+00:00', 0),
            (5, 5, member_id, 'signed_in', '2025-06-01T06:30:00+00:00', 0),
            (6, 6, member_id, 'absent', '2026-06-10T06:30:00+00:00', 0),
        ]
        connection.executemany(
            'INSERT INTO attendances (id, activity_id, member_id, status, signed_in_at, gps_checked) VALUES (?, ?, ?, ?, ?, ?)',
            rows,
        )


def _client(tmp_path):
    db_path = tmp_path / 'checkin_stats.db'
    database_module.DB_PATH = db_path
    init_db(db_path)
    _seed_member_and_attendances(db_path)
    return app.test_client() if hasattr(app, 'test_client') else None


def test_checkin_stats_returns_streak_and_dates(tmp_path, monkeypatch):
    db_path = tmp_path / 'checkin_stats.db'
    monkeypatch.setattr(database_module, 'DB_PATH', db_path)
    init_db(db_path)
    _seed_member_and_attendances(db_path)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get('/api/v1/checkin-stats/1')

    assert response.status_code == 200
    payload = response.json()['data']
    assert payload['member_id'] == 1
    assert payload['current_streak_days'] == 2
    assert payload['longest_streak_days'] == 2
    assert payload['month_checkin_days'] == 3
    assert payload['checkin_dates'] == ['2025-07-01', '2026-06-06', '2026-06-08', '2026-06-09']


def test_checkin_heatmap_groups_by_day(tmp_path, monkeypatch):
    db_path = tmp_path / 'checkin_heatmap.db'
    monkeypatch.setattr(database_module, 'DB_PATH', db_path)
    init_db(db_path)
    _seed_member_and_attendances(db_path)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            'INSERT INTO attendances (activity_id, member_id, status, signed_in_at, gps_checked) VALUES (?, ?, ?, ?, ?)',
            (7, 1, 'signed_in', '2026-06-09T09:00:00+00:00', 0),
        )

    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get('/api/v1/checkin-heatmap/1')

    assert response.status_code == 200
    assert response.json()['data'] == [
        {'date': '2025-07-01', 'count': 1},
        {'date': '2026-06-06', 'count': 1},
        {'date': '2026-06-08', 'count': 1},
        {'date': '2026-06-09', 'count': 2},
    ]


def test_checkin_stats_returns_not_found_for_missing_member(tmp_path, monkeypatch):
    db_path = tmp_path / 'checkin_missing.db'
    monkeypatch.setattr(database_module, 'DB_PATH', db_path)
    init_db(db_path)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get('/api/v1/checkin-stats/999')

    assert response.status_code == 404
    assert response.json() == {'detail': '成员不存在'}