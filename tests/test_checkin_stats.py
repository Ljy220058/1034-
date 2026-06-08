from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def _seed_member_and_attendance(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute(
            """
            INSERT INTO members (name, phone, role, running_years, pace, usual_distance_km, training_goal, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                '张三',
                '13800000000',
                'member',
                3,
                '5:30',
                10.0,
                '保持跑步习惯',
                '2026-01-01T00:00:00+00:00',
                '2026-01-01T00:00:00+00:00',
            ),
        )
        member_id = connection.execute('SELECT id FROM members WHERE phone = ?', ('13800000000',)).fetchone()['id']
        connection.execute(
            """
            INSERT INTO activities (title, start_time, location, route, distance_km, pace_group, description, max_participants, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                '晨跑',
                '2026-01-01T06:00:00+00:00',
                '公园',
                None,
                5.0,
                None,
                None,
                30,
                '2026-01-01T00:00:00+00:00',
                '2026-01-01T00:00:00+00:00',
            ),
        )
        activity_id = connection.execute('SELECT id FROM activities WHERE title = ?', ('晨跑',)).fetchone()['id']
        for day in ('2026-05-01T06:00:00+00:00', '2026-05-02T06:00:00+00:00', '2026-05-04T06:00:00+00:00'):
            connection.execute(
                """
                INSERT INTO attendances (activity_id, member_id, status, signed_in_at, gps_checked)
                VALUES (?, ?, ?, ?, ?)
                """,
                (activity_id, member_id, 'signed_in', day, 1),
            )
        connection.execute(
            """
            INSERT INTO attendances (activity_id, member_id, status, signed_in_at, gps_checked)
            VALUES (?, ?, ?, ?, ?)
            """,
            (activity_id, member_id, 'absent', '2026-05-03T06:00:00+00:00', 0),
        )
        connection.commit()
    return member_id


def test_checkin_stats_returns_streak_and_month_counts() -> None:
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test.db'
        import backend.repository as repository

        original_db_path = repository.DB_PATH
        repository.DB_PATH = db_path
        try:
            _seed_member_and_attendance(db_path)
            response = client.get('/api/v1/checkin-stats/1')
            assert response.status_code == 200
            payload = response.json()
            assert payload['message'] == '签到统计获取成功'
            assert payload['data']['current_streak_days'] == 0
            assert payload['data']['longest_streak_days'] == 2
            assert payload['data']['checkin_days_this_month'] == 0
            assert payload['data']['recent_checkin_dates'] == ['2026-05-01', '2026-05-02', '2026-05-04']
        finally:
            repository.DB_PATH = original_db_path


def test_checkin_heatmap_groups_daily_counts() -> None:
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test.db'
        import backend.repository as repository

        original_db_path = repository.DB_PATH
        repository.DB_PATH = db_path
        try:
            _seed_member_and_attendance(db_path)
            response = client.get('/api/v1/checkin-heatmap/1')
            assert response.status_code == 200
            payload = response.json()
            assert payload['message'] == '热力图数据获取成功'
            assert payload['data'] == [
                {'date': '2026-05-01', 'count': 1},
                {'date': '2026-05-02', 'count': 1},
                {'date': '2026-05-04', 'count': 1},
            ]
        finally:
            repository.DB_PATH = original_db_path


def test_checkin_stats_rejects_invalid_member_id() -> None:
    response = client.get('/api/v1/checkin-stats/0')
    assert response.status_code == 422
    assert response.json() == {'detail': '成员ID必须大于 0'}
