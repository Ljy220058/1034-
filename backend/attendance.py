from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Optional, Tuple

from .database import connect, init_db

AttendanceResult = Tuple[dict[str, Any] | None, str]


@dataclass(frozen=True)
class Attendance:
    id: int
    activity_id: int
    member_id: int
    status: str
    signed_in_at: datetime
    gps_checked: bool

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        data = {
            'id': self.id,
            'activity_id': self.activity_id,
            'member_id': self.member_id,
            'status': self.status,
            'signed_in_at': self.signed_in_at.isoformat(),
            'gps_checked': self.gps_checked,
        }
        return data


def _row_to_attendance(row: sqlite3.Row) -> Attendance:
    signed_in_at = datetime.fromisoformat(row['signed_in_at'])
    if signed_in_at.tzinfo is None:
        signed_in_at = signed_in_at.replace(tzinfo=timezone.utc)
    return Attendance(
        id=row['id'],
        activity_id=row['activity_id'],
        member_id=row['member_id'],
        status=row['status'],
        signed_in_at=signed_in_at,
        gps_checked=bool(row['gps_checked']),
    )


def get_attendance(attendance_id: int) -> Attendance | None:
    with connect() as connection:
        row = connection.execute('SELECT * FROM attendances WHERE id = ?', (attendance_id,)).fetchone()
    return None if row is None else _row_to_attendance(row)


def create_attendance(activity_id: int, member_id: int, *, gps_checked: bool = False, checked_in_at: Optional[datetime] = None) -> tuple[Attendance | None, str]:
    init_db()
    signed_in_at = checked_in_at or datetime.now(timezone.utc)
    if signed_in_at.tzinfo is None:
        signed_in_at = signed_in_at.replace(tzinfo=timezone.utc)
    with connect() as connection:
        activity = connection.execute('SELECT id FROM activities WHERE id = ?', (activity_id,)).fetchone()
        member = connection.execute('SELECT id FROM members WHERE id = ?', (member_id,)).fetchone()
        if activity is None or member is None:
            return None, 'not_found'
        registration = connection.execute(
            "SELECT status FROM registrations WHERE activity_id = ? AND member_id = ? AND status = 'registered'",
            (activity_id, member_id),
        ).fetchone()
        if registration is None:
            return None, 'not_registered'
        existing = connection.execute(
            'SELECT * FROM attendances WHERE activity_id = ? AND member_id = ?',
            (activity_id, member_id),
        ).fetchone()
        if existing is not None:
            # 保留原有签到时间（若无新时间传入）
            keep_at = existing['signed_in_at'] if checked_in_at is None else signed_in_at
            connection.execute(
                'UPDATE attendances SET status = ?, signed_in_at = ?, gps_checked = ? WHERE id = ?',
                ('signed_in', keep_at if isinstance(keep_at, str) else keep_at.isoformat(), int(gps_checked), existing['id']),
            )
            row = connection.execute('SELECT * FROM attendances WHERE id = ?', (existing['id'],)).fetchone()
            return _row_to_attendance(row), 'updated'
        cursor = connection.execute(
            'INSERT INTO attendances(activity_id, member_id, status, signed_in_at, gps_checked) VALUES (?, ?, ?, ?, ?)',
            (activity_id, member_id, 'signed_in', signed_in_at.isoformat(), int(gps_checked)),
        )
        row = connection.execute('SELECT * FROM attendances WHERE id = ?', (cursor.lastrowid,)).fetchone()
        return _row_to_attendance(row), 'created'


def list_attendance(activity_id: int) -> list[Attendance]:
    with connect() as connection:
        rows = connection.execute('SELECT * FROM attendances WHERE activity_id = ? ORDER BY id DESC', (activity_id,)).fetchall()
    return [_row_to_attendance(row) for row in rows]


def delete_attendance(attendance_id: int) -> bool:
    with connect() as connection:
        cursor = connection.execute('DELETE FROM attendances WHERE id = ?', (attendance_id,))
    return cursor.rowcount > 0
