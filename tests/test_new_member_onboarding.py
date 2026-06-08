from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from backend.app import app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    yield TestClient(app)


def _setup_db(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            '''
            CREATE TABLE members (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT,
                role TEXT NOT NULL DEFAULT 'member',
                running_years INTEGER NOT NULL DEFAULT 0,
                pace TEXT,
                pace_group TEXT,
                usual_distance_km REAL,
                training_goal TEXT
            );
            CREATE TABLE activities (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                start_time TEXT NOT NULL,
                location TEXT NOT NULL,
                route TEXT,
                distance_km REAL,
                pace_group TEXT,
                description TEXT,
                max_participants INTEGER
            );
            CREATE TABLE attendances (
                id INTEGER PRIMARY KEY,
                activity_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                signed_in_at TEXT NOT NULL,
                gps_checked INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE member_groups (
                id INTEGER PRIMARY KEY,
                member_id INTEGER NOT NULL,
                group_name TEXT NOT NULL,
                joined_at TEXT NOT NULL
            );
            INSERT INTO members (id, name, phone, role, running_years, pace_group, usual_distance_km, training_goal)
            VALUES
                (1, '新人甲', '13800000001', 'member', 1, '5:00', 5.0, '完成人生第一场半马'),
                (2, '老成员乙', '13800000002', 'member', 8, '4:30', 10.0, '稳定带新');
            INSERT INTO activities (id, title, start_time, location, distance_km, pace_group)
            VALUES (10, '周末晨跑', '2026-06-01T07:00:00', '公园', 10, '5:30');
            INSERT INTO attendances (activity_id, member_id, status, signed_in_at, gps_checked)
            VALUES (10, 1, 'signed_in', '2026-06-01T07:10:00', 1);
            INSERT INTO member_groups (member_id, group_name, joined_at)
            VALUES (1, '新成员微信群', '2026-06-01T06:50:00');
            '''
        )
        connection.commit()
    finally:
        connection.close()


@pytest.fixture()
def temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    db_path = tmp_path / 'running_club.db'
    _setup_db(db_path)
    monkeypatch.setattr('backend.routes.new_member_onboarding.DB_PATH', db_path)
    return db_path


def test_onboarding_status_returns_progress(client: TestClient, temp_db: Path) -> None:
    response = client.get('/api/v1/onboarding/status/1')
    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['member']['name'] == '新人甲'
    assert payload['data']['completion']['profile_completed'] is True
    assert payload['data']['completion']['first_checkin_completed'] is True
    assert payload['data']['completion']['first_activity_completed'] is True
    assert payload['data']['completion']['wechat_group_joined'] is True


def test_onboarding_pair_and_checklist(client: TestClient, temp_db: Path) -> None:
    pair_response = client.post('/api/v1/onboarding/pair', json={'member_id': 1})
    assert pair_response.status_code == 200
    pair_payload = pair_response.json()
    assert pair_payload['data']['new_member_id'] == 1
    assert pair_payload['data']['mentor_member_id'] == 2

    checklist_response = client.get('/api/v1/onboarding/welcome-checklist/1')
    assert checklist_response.status_code == 200
    checklist_payload = checklist_response.json()
    assert checklist_payload['data']['member_id'] == 1
    assert checklist_payload['data']['all_completed'] is True
    assert len(checklist_payload['data']['items']) == 4
