from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

import pytest

from backend import repository


class TrackingConnection:
    """SQLite connection wrapper that records UPDATE statements.

    Args:
        connection: Backing SQLite connection.
        captured: Mutable capture dictionary.
    """

    def __init__(self, connection: sqlite3.Connection, captured: dict[str, Any]) -> None:
        self._connection = connection
        self._captured = captured
        self.row_factory = connection.row_factory

    def __enter__(self) -> TrackingConnection:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def execute(self, sql: str, params: Any = ()) -> sqlite3.Cursor:
        if sql.startswith('UPDATE members SET') or sql.startswith('UPDATE announcements SET') or sql.startswith('UPDATE activities SET'):
            self._captured['sql'] = sql
            self._captured['params'] = params
            return self._connection.execute('SELECT 1')
        return self._connection.execute(sql, params)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._connection, item)


def test_build_update_parts_whitelists_columns() -> None:
    """Build update clauses from a fixed whitelist only.

    Returns:
        None.
    """
    assignments, params = repository._build_update_parts(
        {'name': 'Alice', 'role': 'admin', 'sql': 'DROP TABLE members;'},
        repository._UPDATE_FIELD_MAPS['members'],
    )
    assert assignments == ['name = ?', 'role = ?']
    assert params == ['Alice', 'admin']


def test_update_member_uses_parameterized_whitelist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Update members with only whitelisted fields and parameter binding.

    Returns:
        None.
    """
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            role TEXT NOT NULL,
            running_years INTEGER NOT NULL,
            pace TEXT,
            usual_distance_km REAL,
            training_goal TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO members (name, phone, role, running_years, pace, usual_distance_km, training_goal)
        VALUES ('原名', '13800000000', 'member', 1, '6:00', 10.0, '保持');
        """
    )
    captured: dict[str, Any] = {}
    monkeypatch.setattr(repository, 'initialize_database', lambda: None)
    monkeypatch.setattr(repository, 'connect', lambda: TrackingConnection(conn, captured))

    class Payload:
        def model_dump(self, exclude_unset: bool = False) -> dict[str, Any]:
            return {'name': '新名', 'role': 'leader', 'sql': 'DROP TABLE members;'}

    member = repository.update_member(1, Payload())
    assert member is not None
    assert member.name == '原名'
    assert captured['sql'] == 'UPDATE members SET name = ?, role = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?'
    assert captured['params'] == ['新名', 'leader', 1]


def test_update_announcement_maps_body_and_uses_whitelist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Update announcements with the body alias mapped to the body column.

    Returns:
        None.
    """
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL,
            is_pinned INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO announcements (title, body, status, is_pinned)
        VALUES ('旧标题', '旧内容', 'draft', 0);
        """
    )
    captured: dict[str, Any] = {}
    monkeypatch.setattr(repository, 'initialize_database', lambda: None)
    monkeypatch.setattr(repository, 'connect', lambda: TrackingConnection(conn, captured))

    class Payload:
        def model_dump(self, exclude_unset: bool = False) -> dict[str, Any]:
            return {'content': '新内容', 'is_pinned': True}

    announcement = repository.update_announcement(1, Payload())
    assert announcement is not None
    assert announcement.body == '旧内容'
    assert captured['sql'] == 'UPDATE announcements SET body = ?, is_pinned = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?'
    assert captured['params'] == ['新内容', True, 1]


def test_update_activity_only_updates_whitelisted_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Update activities using a fixed column whitelist.

    Returns:
        None.
    """
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            start_time TEXT NOT NULL,
            location TEXT NOT NULL,
            route TEXT,
            distance_km REAL,
            pace_group TEXT,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO activities (title, start_time, location, route, distance_km, pace_group, description)
        VALUES ('晨跑', '2026-06-06T08:00:00+00:00', '公园', '环线', 5.0, '6:00', '早晨训练');
        """
    )
    captured: dict[str, Any] = {}
    monkeypatch.setattr(repository, 'initialize_database', lambda: None)
    monkeypatch.setattr(repository, 'connect', lambda: TrackingConnection(conn, captured))

    class Payload:
        def model_dump(self, exclude_unset: bool = False) -> dict[str, Any]:
            return {'title': '夜跑', 'start_time': datetime(2026, 6, 6, 9, 0, tzinfo=timezone.utc), 'sql': 'DROP TABLE activities;'}

    activity = repository.update_activity(1, Payload())
    assert activity is not None
    assert activity.title == '晨跑'
    assert captured['sql'] == 'UPDATE activities SET title = ?, start_time = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?'
    assert captured['params'][0] == '夜跑'
    assert captured['params'][1] == '2026-06-06T09:00:00+00:00'
    assert captured['params'][2] == 1
