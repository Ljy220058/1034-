from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from backend import database as database_module
from backend.app import app
from backend.routes import checkin_stats as checkin_stats_module

client = TestClient(app, raise_server_exceptions=False)


def _seed_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute('CREATE TABLE members (id INTEGER PRIMARY KEY, name TEXT NOT NULL)')
        connection.execute(
            '''
            CREATE TABLE attendances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                signed_in_at TEXT NOT NULL,
                status TEXT NOT NULL,
                gps_checked INTEGER NOT NULL DEFAULT 0
            )
            '''
        )
        connection.execute('INSERT INTO members (id, name) VALUES (1, "张三")')
        rows = [
            (1, 1, 1, '2026-06-01T08:00:00+00:00', 'signed_in'),
            (2, 1, 1, '2026-06-02T08:00:00+00:00', 'signed_in'),
            (3, 1, 1, '2026-06-02T09:00:00+00:00', 'signed_in'),
            (4, 1, 1, '2026-06-04T08:00:00+00:00', 'signed_in'),
            (5, 1, 1, '2025-05-01T08:00:00+00:00', 'signed_in'),
            (6, 1, 1, '2025-01-01T08:00:00+00:00', 'absent'),
        ]
        connection.executemany(
            'INSERT INTO attendances (id, activity_id, member_id, signed_in_at, status) VALUES (?, ?, ?, ?, ?)',
            rows,
        )
        connection.commit()


def test_checkin_stats_returns_api_response(tmp_path: Path, monkeypatch) -> None:
    """签到统计接口应返回 ApiResponse。"""
    db_path = tmp_path / 'checkin_stats.db'
    _seed_db(db_path)
    monkeypatch.setattr(database_module, 'DB_PATH', db_path)
    monkeypatch.setattr(checkin_stats_module, 'DB_PATH', db_path)

    response = client.get('/api/v1/checkin-stats/1')

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['member_id'] == 1
    assert payload['data']['current_streak_days'] == 2
    assert payload['data']['longest_streak_days'] == 2
    assert payload['data']['month_checkin_days'] == 3
    assert payload['data']['checkin_dates'] == ['2025-05-01', '2026-06-01', '2026-06-02', '2026-06-04']


def test_checkin_heatmap_returns_year_data(tmp_path: Path, monkeypatch) -> None:
    """签到热力图接口应返回近一年的日期统计。"""
    db_path = tmp_path / 'checkin_heatmap.db'
    _seed_db(db_path)
    monkeypatch.setattr(database_module, 'DB_PATH', db_path)
    monkeypatch.setattr(checkin_stats_module, 'DB_PATH', db_path)

    response = client.get('/api/v1/checkin-heatmap/1')

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert len(payload['data']) == 365
    assert any(item['date'] == '2026-06-01' and item['count'] == 1 for item in payload['data'])
    assert any(item['date'] == '2026-06-02' and item['count'] == 2 for item in payload['data'])


def test_checkin_stats_missing_member_returns_structured_error(tmp_path: Path, monkeypatch) -> None:
    """成员不存在时应返回中文结构化错误。"""
    db_path = tmp_path / 'checkin_missing.db'
    _seed_db(db_path)
    monkeypatch.setattr(database_module, 'DB_PATH', db_path)
    monkeypatch.setattr(checkin_stats_module, 'DB_PATH', db_path)

    response = client.get('/api/v1/checkin-stats/999')

    assert response.status_code == 404
    assert response.json() == {'detail': '成员不存在'}
