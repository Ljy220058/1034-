#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

BADGE_THRESHOLDS = [
    {'level': '新手上路', 'min_total_km': 1},
    {'level': '稳定打卡', 'min_total_km': 20},
    {'level': '长距离达人', 'min_total_km': 80},
    {'level': '跑团核心', 'min_total_km': 200},
]

@dataclass(frozen=True)
class RunRecord:
    record_key: str
    member_id: int
    activity_id: int
    activity_date: date
    distance_km: float


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    raw = str(value).strip().replace('Z', '+00:00')
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None


def _round_km(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def _week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?", (table,)).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {str(row['name']) for row in conn.execute(f'PRAGMA table_info({table})').fetchall()}


def _load_members(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cols = _columns(conn, 'members')
    if not {'id'}.issubset(cols):
        return []
    name_expr = 'name' if 'name' in cols else ('nickname' if 'nickname' in cols else "''")
    rows = conn.execute(f'SELECT id AS member_id, COALESCE({name_expr}, "") AS nickname FROM members ORDER BY id ASC').fetchall()
    return [{'member_id': int(row['member_id']), 'nickname': str(row['nickname'] or f"member-{row['member_id']}")} for row in rows]


def _load_signed_in_records(conn: sqlite3.Connection) -> list[RunRecord]:
    required_tables = {'activities', 'attendances'}
    if any(not _table_exists(conn, table) for table in required_tables):
        return []
    activity_cols = _columns(conn, 'activities')
    attendance_cols = _columns(conn, 'attendances')
    if not {'id', 'distance_km'}.issubset(activity_cols) or not {'activity_id', 'member_id'}.issubset(attendance_cols):
        return []
    activity_time_col = 'start_time' if 'start_time' in activity_cols else ('activity_start_time' if 'activity_start_time' in activity_cols else None)
    if activity_time_col is None:
        return []
    attendance_status_col = 'status' if 'status' in attendance_cols else None
    status_filter = "WHERE COALESCE(att.status, 'signed_in') = 'signed_in'" if attendance_status_col else ''
    rows = conn.execute(
        f'''
        SELECT
            att.member_id AS member_id,
            att.activity_id AS activity_id,
            a.{activity_time_col} AS activity_time,
            COALESCE(a.distance_km, 0) AS distance_km
        FROM attendances att
        JOIN activities a ON a.id = att.activity_id
        {status_filter}
        ORDER BY att.member_id ASC, att.activity_id ASC
        '''
    ).fetchall()
    records: list[RunRecord] = []
    seen: set[tuple[int, int]] = set()
    for row in rows:
        try:
            member_id = int(row['member_id'])
            activity_id = int(row['activity_id'])
            distance_km = float(row['distance_km'] or 0)
        except (TypeError, ValueError):
            continue
        if distance_km < 0:
            continue
        activity_date = _parse_date(row['activity_time'])
        if activity_date is None:
            continue
        dedupe_key = (member_id, activity_id)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        records.append(RunRecord(record_key=f'{member_id}:{activity_id}', member_id=member_id, activity_id=activity_id, activity_date=activity_date, distance_km=distance_km))
    return records


def _badge_for(total_km: float) -> dict[str, Any] | None:
    earned = [badge for badge in BADGE_THRESHOLDS if total_km >= float(badge['min_total_km'])]
    return earned[-1] if earned else None


def _next_gap(total_km: float) -> dict[str, Any] | None:
    for badge in BADGE_THRESHOLDS:
        threshold = float(badge['min_total_km'])
        if total_km < threshold:
            return {'next_level': badge['level'], 'remaining_km': _round_km(threshold - total_km)}
    return None


def build_badge_payload(db_path: Path, as_of: date) -> dict[str, Any]:
    with _connect(db_path) as conn:
        members = _load_members(conn)
        records = _load_signed_in_records(conn)
    week_start = _week_start(as_of)
    month_start = _month_start(as_of)
    by_member: dict[int, list[RunRecord]] = {}
    for record in records:
        by_member.setdefault(record.member_id, []).append(record)
    result_members = []
    for member in members:
        member_id = int(member['member_id'])
        member_records = by_member.get(member_id, [])
        week_km = sum(r.distance_km for r in member_records if week_start <= r.activity_date <= as_of)
        month_km = sum(r.distance_km for r in member_records if month_start <= r.activity_date <= as_of)
        total_km = sum(r.distance_km for r in member_records if r.activity_date <= as_of)
        result_members.append({
            'member_id': member_id,
            'nickname': member['nickname'],
            'mileage': {'week_km': _round_km(week_km), 'month_km': _round_km(month_km), 'total_km': _round_km(total_km)},
            'earned_badge': _badge_for(total_km),
            'next_level_gap': _next_gap(total_km),
        })
    result_members.sort(key=lambda item: (-item['mileage']['total_km'], -item['mileage']['month_km'], item['member_id']))
    return {'generated_as_of': as_of.isoformat(), 'source_db': str(db_path), 'badge_thresholds_km': BADGE_THRESHOLDS, 'member_count': len(result_members), 'members': result_members}


def _init_demo_schema(conn: sqlite3.Connection) -> None:
    conn.executescript('''
        CREATE TABLE members (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE activities (id INTEGER PRIMARY KEY, title TEXT, start_time TEXT, location TEXT, distance_km REAL);
        CREATE TABLE attendances (id INTEGER PRIMARY KEY, activity_id INTEGER, member_id INTEGER, status TEXT, signed_in_at TEXT);
    ''')


def _self_check_case(name: str, rows: Iterable[str]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f'mileage-badge-{name}-') as tmp:
        db_path = Path(tmp) / 'case.db'
        with sqlite3.connect(db_path) as conn:
            _init_demo_schema(conn)
            for sql in rows:
                conn.execute(sql)
        payload = build_badge_payload(db_path, date(2026, 6, 6))
        json.dumps(payload, ensure_ascii=False)
        return {'ok': True, 'member_count': payload['member_count']}


def run_self_check() -> dict[str, Any]:
    cases = {
        'empty_data': _self_check_case('empty', []),
        'missing_fields': _self_check_case('missing', [
            "INSERT INTO members(id, name) VALUES (1, NULL)",
            "INSERT INTO activities(id, title, start_time, location, distance_km) VALUES (1, '缺少距离', 'bad-date', '操场', NULL)",
            "INSERT INTO attendances(id, activity_id, member_id, status, signed_in_at) VALUES (1, 1, 1, 'signed_in', NULL)",
        ]),
        'duplicate_records': _self_check_case('duplicate', [
            "INSERT INTO members(id, name) VALUES (1, '重复样例')",
            "INSERT INTO activities(id, title, start_time, location, distance_km) VALUES (1, '晨跑', '2026-06-02T07:00:00', '操场', 5.0)",
            "INSERT INTO attendances(id, activity_id, member_id, status, signed_in_at) VALUES (1, 1, 1, 'signed_in', '2026-06-02T07:05:00')",
            "INSERT INTO attendances(id, activity_id, member_id, status, signed_in_at) VALUES (2, 1, 1, 'signed_in', '2026-06-02T07:06:00')",
        ]),
    }
    return {'self_check': {'ok': all(case['ok'] for case in cases.values()), 'cases': cases}}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='根据跑团成员签到跑量生成里程徽章 JSON。')
    parser.add_argument('--db', default=os.getenv('RUNNING_CLUB_DB_PATH', './data/running_club.db'), help='SQLite 数据库路径，默认读取 RUNNING_CLUB_DB_PATH 或 ./data/running_club.db')
    parser.add_argument('--as-of', default=date.today().isoformat(), help='统计截止日期，格式 YYYY-MM-DD；本周按 ISO 周一开始，本月按自然月开始')
    parser.add_argument('--output', help='可选输出文件路径；不提供时输出到 stdout')
    parser.add_argument('--self-check', action='store_true', help='运行空数据、缺少字段、重复记录三类基础自检并输出 JSON')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.self_check:
        payload = run_self_check()
    else:
        payload = build_badge_payload(Path(args.db), date.fromisoformat(args.as_of))
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding='utf-8')
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
