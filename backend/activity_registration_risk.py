from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from .database import connect
from .db import initialize_database


@dataclass(frozen=True)
class ActivityRecord:
    """SQLite activity row exposed to routes."""

    id: int
    title: str
    start_time: str
    location: str
    route: str | None
    distance_km: float | None
    pace_group: str | None
    description: str | None
    max_participants: int | None
    created_at: str
    updated_at: str

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class RegistrationRecord:
    """SQLite registration row exposed to routes."""

    id: int
    activity_id: int
    member_id: int
    status: str
    created_at: str

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        return self.__dict__.copy()


def _payload_dict(payload: Any, *, exclude_unset: bool = False) -> dict[str, Any]:
    if hasattr(payload, 'model_dump'):
        return payload.model_dump(exclude_unset=exclude_unset)
    return dict(payload)


def _activity_from_row(row: sqlite3.Row | None) -> ActivityRecord | None:
    if row is None:
        return None
    return ActivityRecord(
        id=int(row['id']), title=str(row['title']), start_time=str(row['start_time']), location=str(row['location']),
        route=row['route'], distance_km=row['distance_km'], pace_group=row['pace_group'], description=row['description'],
        max_participants=row['max_participants'], created_at=str(row['created_at']), updated_at=str(row['updated_at']),
    )


def _registration_from_row(row: sqlite3.Row | None) -> RegistrationRecord | None:
    if row is None:
        return None
    return RegistrationRecord(
        id=int(row['id']), activity_id=int(row['activity_id']), member_id=int(row['member_id']),
        status=str(row['status']), created_at=str(row['created_at']),
    )


def _registration_status_from_row(row: sqlite3.Row | None) -> str:
    """将报名记录转换为活动响应里的报名状态。

    Args:
        row: SQLite 报名记录。

    Returns:
        报名状态；无记录时返回未报名。
    """
    if row is None or row['status'] != 'registered':
        return 'not_registered'
    return 'registered'


def _ensure_activity_columns() -> None:
    initialize_database()
    with connect() as connection:
        columns = {row['name'] for row in connection.execute('PRAGMA table_info(activities)').fetchall()}
        if 'max_participants' not in columns:
            connection.execute('ALTER TABLE activities ADD COLUMN max_participants INTEGER CHECK (max_participants IS NULL OR max_participants > 0)')


def get_activity(activity_id: int) -> ActivityRecord | None:
    _ensure_activity_columns()
    with connect() as connection:
        row = connection.execute('SELECT * FROM activities WHERE id = ?', (activity_id,)).fetchone()
    return _activity_from_row(row)


def list_activities() -> list[ActivityRecord]:
    _ensure_activity_columns()
    with connect() as connection:
        rows = connection.execute('SELECT * FROM activities ORDER BY id DESC').fetchall()
    return [activity for row in rows if (activity := _activity_from_row(row)) is not None]


def get_registration_status(activity_id: int, member_id: int | None) -> str:
    """读取成员对单个活动的报名状态。

    Args:
        activity_id: 活动编号。
        member_id: 成员编号；未登录时为 None。

    Returns:
        registered 或 not_registered。
    """
    if member_id is None:
        return 'not_registered'
    _ensure_activity_columns()
    with connect() as connection:
        row = connection.execute(
            'SELECT status FROM registrations WHERE activity_id = ? AND member_id = ?',
            (activity_id, member_id),
        ).fetchone()
    return _registration_status_from_row(row)


def list_registration_statuses(activity_ids: list[int], member_id: int | None) -> dict[int, str]:
    """批量读取成员对活动列表的报名状态。

    Args:
        activity_ids: 活动编号列表。
        member_id: 成员编号；未登录时为 None。

    Returns:
        以活动编号为键的报名状态字典。
    """
    statuses = {activity_id: 'not_registered' for activity_id in activity_ids}
    if member_id is None or not activity_ids:
        return statuses
    with connect() as connection:
        rows = connection.execute(
            '''
            SELECT activity_id, status
            FROM registrations
            WHERE member_id = ?
            ''',
            (member_id,),
        ).fetchall()
    activity_id_set = set(activity_ids)
    for row in rows:
        activity_id = int(row['activity_id'])
        if activity_id in activity_id_set:
            statuses[activity_id] = _registration_status_from_row(row)
    return statuses


def create_activity(payload: Any) -> ActivityRecord:
    _ensure_activity_columns()
    data = _payload_dict(payload)
    with connect() as connection:
        cursor = connection.execute(
            '''
            INSERT INTO activities (title, start_time, location, route, distance_km, pace_group, description, max_participants)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (data.get('title'), data.get('start_time').isoformat(), data.get('location'), data.get('route'),
             data.get('distance_km'), data.get('pace_group'), data.get('description'), data.get('max_participants')),
        )
        row = connection.execute('SELECT * FROM activities WHERE id = ?', (cursor.lastrowid,)).fetchone()
    return _activity_from_row(row)


def update_activity(activity_id: int, payload: Any) -> ActivityRecord | None:
    _ensure_activity_columns()
    data = _payload_dict(payload, exclude_unset=True)
    allowed = ['title', 'start_time', 'location', 'route', 'distance_km', 'pace_group', 'description', 'max_participants']
    updates = [(key, data[key].isoformat() if key == 'start_time' else data[key]) for key in allowed if key in data]
    if updates:
        assignments = ', '.join(f'{key} = ?' for key, _ in updates)
        with connect() as connection:
            connection.execute(f'UPDATE activities SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', [*map(lambda item: item[1], updates), activity_id])
    return get_activity(activity_id)


def delete_activity(activity_id: int) -> bool:
    _ensure_activity_columns()
    with connect() as connection:
        cursor = connection.execute('DELETE FROM activities WHERE id = ?', (activity_id,))
    return cursor.rowcount > 0


def _registered_count(connection: sqlite3.Connection, activity_id: int) -> int:
    row = connection.execute("SELECT COUNT(*) AS count FROM registrations WHERE activity_id = ? AND status = 'registered'", (activity_id,)).fetchone()
    return int(row['count'])


def create_registration(activity_id: int, member_id: int) -> tuple[RegistrationRecord | None, str]:
    _ensure_activity_columns()
    with connect() as connection:
        activity = connection.execute('SELECT * FROM activities WHERE id = ?', (activity_id,)).fetchone()
        member = connection.execute('SELECT id FROM members WHERE id = ?', (member_id,)).fetchone()
        if activity is None or member is None:
            return None, 'not_found'
        existing = connection.execute('SELECT * FROM registrations WHERE activity_id = ? AND member_id = ?', (activity_id, member_id)).fetchone()
        if existing is not None and existing['status'] == 'registered':
            return _registration_from_row(existing), 'conflict'
        quota = activity['max_participants']
        if quota is not None and _registered_count(connection, activity_id) >= int(quota):
            return None, 'full'
        if existing is not None:
            connection.execute("UPDATE registrations SET status = 'registered' WHERE id = ?", (existing['id'],))
            row = connection.execute('SELECT * FROM registrations WHERE id = ?', (existing['id'],)).fetchone()
            return _registration_from_row(row), 'created'
        cursor = connection.execute('INSERT INTO registrations (activity_id, member_id) VALUES (?, ?)', (activity_id, member_id))
        row = connection.execute('SELECT * FROM registrations WHERE id = ?', (cursor.lastrowid,)).fetchone()
    return _registration_from_row(row), 'created'


def cancel_registration(activity_id: int, member_id: int) -> RegistrationRecord | None:
    _ensure_activity_columns()
    with connect() as connection:
        row = connection.execute('SELECT * FROM registrations WHERE activity_id = ? AND member_id = ?', (activity_id, member_id)).fetchone()
        if row is None or row['status'] == 'cancelled':
            return None
        connection.execute("UPDATE registrations SET status = 'cancelled' WHERE id = ?", (row['id'],))
        cancelled = connection.execute('SELECT * FROM registrations WHERE id = ?', (row['id'],)).fetchone()
    return _registration_from_row(cancelled)


def registration_risk_smoke_panel(activity: ActivityRecord) -> dict[str, Any]:
    quota = activity.max_participants or '不限'
    return {
        'title': '活动报名风险冒烟测试面板',
        'activity_id': activity.id,
        'acceptance_checklist': ['正常报名返回 201', '超出名额返回 409', '重复报名返回 409', '取消后重新报名返回 201'],
        'scenarios': [
            {'title': '正常报名', 'test_data': f'活动名额 {quota}，成员未报名', 'steps': ['创建活动', '成员提交报名'], 'expected_result': '返回 201 且状态为 registered', 'failure_hint': '正常报名失败：请检查报名写入流程'},
            {'title': '超出名额', 'test_data': '活动已达到人数上限，新增成员继续报名', 'steps': ['填满活动名额', '另一成员提交报名'], 'expected_result': '返回 409 且提示名额已满', 'failure_hint': '超额报名未拦截：请检查名额上限规则'},
            {'title': '重复报名', 'test_data': '同一成员已处于 registered 状态', 'steps': ['成员首次报名', '同一成员再次报名'], 'expected_result': '返回 409 且提示已报名', 'failure_hint': '重复报名未拦截：请检查唯一报名规则'},
            {'title': '取消后重新报名', 'test_data': '同一成员报名后取消', 'steps': ['成员取消报名', '同一成员再次报名'], 'expected_result': '返回 201 且恢复 registered 状态', 'failure_hint': '取消后重报失败：请检查 cancelled 状态恢复逻辑'},
        ],
    }
