from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'generate_mileage_badges.py'


def _run_badges(db_path: Path, *extra: str) -> dict:
    result = subprocess.run(
        [str(SCRIPT), '--db', str(db_path), '--as-of', '2026-06-06', *extra],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def _init_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            '''
            CREATE TABLE members (
                id INTEGER PRIMARY KEY,
                name TEXT,
                phone TEXT,
                role TEXT DEFAULT 'member',
                running_years INTEGER DEFAULT 0,
                pace TEXT,
                usual_distance_km REAL,
                training_goal TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE activities (
                id INTEGER PRIMARY KEY,
                title TEXT,
                start_time TEXT,
                location TEXT,
                distance_km REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE registrations (
                id INTEGER PRIMARY KEY,
                activity_id INTEGER,
                member_id INTEGER,
                status TEXT DEFAULT 'registered',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE attendances (
                id INTEGER PRIMARY KEY,
                activity_id INTEGER,
                member_id INTEGER,
                status TEXT DEFAULT 'signed_in',
                signed_in_at TEXT,
                gps_checked INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            '''
        )


def test_badge_generator_outputs_week_month_total_badges_and_next_gap(tmp_path: Path) -> None:
    db_path = tmp_path / 'club.db'
    _init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.executemany('INSERT INTO members(id, name) VALUES (?, ?)', [(1, 'Li Ming'), (2, 'Chen Yu')])
        conn.executemany(
            'INSERT INTO activities(id, title, start_time, location, distance_km) VALUES (?, ?, ?, ?, ?)',
            [
                (1, '本周晨跑', '2026-06-02T07:00:00', '操场', 10.0),
                (2, '本月长跑', '2026-06-05T07:00:00', '公园', 15.0),
                (3, '上月恢复跑', '2026-05-20T07:00:00', '河边', 5.0),
                (4, '未签到不计入', '2026-06-05T09:00:00', '公园', 99.0),
            ],
        )
        conn.executemany(
            'INSERT INTO registrations(id, activity_id, member_id, status) VALUES (?, ?, ?, ?)',
            [(1, 1, 1, 'registered'), (2, 2, 1, 'registered'), (3, 3, 1, 'registered'), (4, 4, 2, 'registered')],
        )
        conn.executemany(
            'INSERT INTO attendances(id, activity_id, member_id, status, signed_in_at) VALUES (?, ?, ?, ?, ?)',
            [
                (1, 1, 1, 'signed_in', '2026-06-02T07:05:00'),
                (2, 2, 1, 'signed_in', '2026-06-05T07:05:00'),
                (3, 3, 1, 'signed_in', '2026-05-20T07:05:00'),
                (4, 4, 2, 'absent', '2026-06-05T09:05:00'),
            ],
        )

    payload = _run_badges(db_path)

    assert payload['generated_as_of'] == '2026-06-06'
    assert payload['badge_thresholds_km'] == [
        {'level': '新手上路', 'min_total_km': 1},
        {'level': '稳定打卡', 'min_total_km': 20},
        {'level': '长距离达人', 'min_total_km': 80},
        {'level': '跑团核心', 'min_total_km': 200},
    ]
    li_ming = payload['members'][0]
    assert li_ming['member_id'] == 1
    assert li_ming['nickname'] == 'Li Ming'
    assert li_ming['mileage'] == {'week_km': 25.0, 'month_km': 25.0, 'total_km': 30.0}
    assert li_ming['earned_badge'] == {'level': '稳定打卡', 'min_total_km': 20}
    assert li_ming['next_level_gap'] == {'next_level': '长距离达人', 'remaining_km': 50.0}
    assert payload['members'][1]['earned_badge'] is None


def test_badge_generator_self_check_covers_empty_missing_fields_and_duplicate_rows(tmp_path: Path) -> None:
    result = subprocess.run(
        [str(SCRIPT), '--self-check'],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload['self_check']['ok'] is True
    assert set(payload['self_check']['cases']) == {'empty_data', 'missing_fields', 'duplicate_records'}
    for case in payload['self_check']['cases'].values():
        assert case['ok'] is True
        assert isinstance(case['member_count'], int)
