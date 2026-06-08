from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .database import connect
from .db import initialize_database


@dataclass(frozen=True)
class MemberRecord:
    """SQLite member row exposed to routes."""

    id: int
    name: str
    phone: str | None
    role: str
    running_years: int
    pace: str | None
    usual_distance_km: float | None
    training_goal: str | None
    created_at: str
    updated_at: str

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        """Serialize the member row.

        Args:
            mode: Serialization mode kept for route compatibility.

        Returns:
            JSON-ready member dictionary.
        """
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'role': self.role,
            'running_years': self.running_years,
            'pace': self.pace,
            'usual_distance_km': self.usual_distance_km,
            'training_goal': self.training_goal,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


@dataclass(frozen=True)
class AnnouncementRecord:
    """SQLite announcement row exposed to routes."""

    id: int
    title: str
    body: str
    status: str
    is_pinned: bool
    created_at: str
    updated_at: str

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        """Serialize the announcement row.

        Args:
            mode: Serialization mode kept for route compatibility.

        Returns:
            JSON-ready announcement dictionary.
        """
        return {
            'id': self.id,
            'title': self.title,
            'body': self.body,
            'content': self.body,
            'status': self.status,
            'is_pinned': self.is_pinned,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


def _member_from_row(row: sqlite3.Row | None) -> MemberRecord | None:
    """Convert a SQLite row to a member record."""
    if row is None:
        return None
    return MemberRecord(
        id=int(row['id']),
        name=str(row['name']),
        phone=row['phone'],
        role=str(row['role']),
        running_years=int(row['running_years'] or 0),
        pace=row['pace'],
        usual_distance_km=row['usual_distance_km'],
        training_goal=row['training_goal'],
        created_at=str(row['created_at']),
        updated_at=str(row['updated_at']),
    )


def _announcement_from_row(row: sqlite3.Row | None) -> AnnouncementRecord | None:
    """Convert a SQLite row to an announcement record."""
    if row is None:
        return None
    return AnnouncementRecord(
        id=int(row['id']),
        title=str(row['title']),
        body=str(row['body']),
        status=str(row['status']),
        is_pinned=bool(row['is_pinned']),
        created_at=str(row['created_at']),
        updated_at=str(row['updated_at']),
    )


def _payload_dict(payload: Any) -> dict[str, Any]:
    """Return a dictionary from a Pydantic model or mapping."""
    if hasattr(payload, 'model_dump'):
        return payload.model_dump(exclude_unset=False)
    return dict(payload)


def get_member(member_id: int) -> MemberRecord | None:
    """Fetch a member by id."""
    initialize_database()
    with connect() as connection:
        row = connection.execute('SELECT * FROM members WHERE id = ?', (member_id,)).fetchone()
    return _member_from_row(row)


def list_members() -> list[MemberRecord]:
    """List members ordered by newest first."""
    initialize_database()
    with connect() as connection:
        rows = connection.execute('SELECT * FROM members ORDER BY id DESC').fetchall()
    return [record for row in rows if (record := _member_from_row(row)) is not None]


def create_member_with_password(payload: Any, password_hash: str) -> tuple[MemberRecord | None, str]:
    """Create a member with a password hash.

    Args:
        payload: Member creation fields.
        password_hash: Precomputed password hash.

    Returns:
        Created member plus outcome label, or conflict.
    """
    initialize_database()
    data = _payload_dict(payload)
    try:
        with connect() as connection:
            cursor = connection.execute(
                '''
                INSERT INTO members (name, phone, role, running_years, pace, usual_distance_km, training_goal, password_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    data.get('name'),
                    data.get('phone'),
                    data.get('role', 'member'),
                    int(data.get('running_years') or 0),
                    data.get('pace'),
                    data.get('usual_distance_km'),
                    data.get('training_goal'),
                    password_hash,
                ),
            )
            row = connection.execute('SELECT * FROM members WHERE id = ?', (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        return None, 'conflict'
    return _member_from_row(row), 'created'


def create_member(payload: Any) -> MemberRecord:
    """Create a member without a password hash."""
    member, outcome = create_member_with_password(payload, '')
    if member is None or outcome == 'conflict':
        raise ValueError('member already exists')
    return member


def update_member(member_id: int, payload: Any) -> MemberRecord | None:
    """Update a member by id."""
    initialize_database()
    data = _payload_dict(payload)
    allowed = ['name', 'phone', 'role', 'running_years', 'pace', 'usual_distance_km', 'training_goal']
    updates = [(key, data[key]) for key in allowed if key in data and data[key] is not None]
    if not updates:
        return get_member(member_id)
    assignments = ', '.join(f'{key} = ?' for key, _ in updates)
    params = [value for _, value in updates]
    params.append(member_id)
    with connect() as connection:
        connection.execute(f'UPDATE members SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', params)
    return get_member(member_id)


def delete_member(member_id: int) -> bool:
    """Delete a member by id."""
    initialize_database()
    with connect() as connection:
        cursor = connection.execute('DELETE FROM members WHERE id = ?', (member_id,))
    return cursor.rowcount > 0


def list_announcements(status: str | None = None) -> list[AnnouncementRecord]:
    """List announcements with an optional status filter."""
    initialize_database()
    with connect() as connection:
        if status is None:
            rows = connection.execute('SELECT * FROM announcements ORDER BY is_pinned DESC, id DESC').fetchall()
        else:
            rows = connection.execute('SELECT * FROM announcements WHERE status = ? ORDER BY is_pinned DESC, id DESC', (status,)).fetchall()
    return [record for row in rows if (record := _announcement_from_row(row)) is not None]


def create_announcement(payload: Any) -> AnnouncementRecord:
    """创建公告。"""
    initialize_database()
    data = _payload_dict(payload)
    sql = "INSERT INTO announcements (title, body, status, is_pinned) VALUES (?, ?, ?, ?)"
    with connect() as connection:
        cursor = connection.execute(
            sql,
            (data.get("title"), data.get("body"), data.get("status", "published"), int(data.get("is_pinned", True))),
        )
        row = connection.execute("SELECT * FROM announcements WHERE id = ?", (cursor.lastrowid,)).fetchone()
    record = _announcement_from_row(row)
    if record is None:
        raise ValueError("announcement creation failed")
    return record


def delete_announcement(announcement_id: int) -> bool:
    """删除公告。"""
    initialize_database()
    with connect() as connection:
        cursor = connection.execute("DELETE FROM announcements WHERE id = ?", (announcement_id,))
    return cursor.rowcount > 0


def get_announcement(announcement_id: int) -> AnnouncementRecord | None:
    """Fetch an announcement by id."""
    initialize_database()
    with connect() as connection:
        row = connection.execute('SELECT * FROM announcements WHERE id = ?', (announcement_id,)).fetchone()
    return _announcement_from_row(row)


def update_announcement(announcement_id: int, payload: Any) -> AnnouncementRecord | None:
    """Update an announcement by id."""
    initialize_database()
    data = _payload_dict(payload)
    allowed = ['title', 'body', 'status', 'is_pinned']
    updates = [(key, data[key]) for key in allowed if key in data and data[key] is not None]
    if not updates:
        return get_announcement(announcement_id)
    assignments = ', '.join(f'{key} = ?' for key, _ in updates)
    params = [int(value) if key == 'is_pinned' else value for key, value in updates]
    params.append(announcement_id)
    with connect() as connection:
        connection.execute(f'UPDATE announcements SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', params)
    return get_announcement(announcement_id)


def get_attendance(attendance_id: int) -> Any:
    """Return no attendance record for compatibility."""
    _ = attendance_id
    return None


def create_attendance(payload: Any) -> Any:
    """Attendance creation is unavailable in this compatibility layer."""
    _ = payload
    return None


def delete_attendance(attendance_id: int) -> bool:
    """Delete no attendance record for compatibility."""
    _ = attendance_id
    return False


def list_activity_attendance(activity_id: int) -> list[Any]:
    """Return empty attendance for compatibility."""
    _ = activity_id
    return []
