from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from .db import initialize_database
from .database import connect
from .models import ActivityCreate, ActivityUpdate, AnnouncementCreate, AnnouncementUpdate, MemberCreate, MemberUpdate


@dataclass
class Member:
    id: int
    name: str
    phone: Optional[str]
    role: str
    running_years: int
    pace: Optional[str]
    usual_distance_km: Optional[float]
    training_goal: Optional[str]
    created_at: datetime
    updated_at: datetime

    def model_dump(self, mode: str = 'python'):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'role': self.role,
            'running_years': self.running_years,
            'pace': self.pace,
            'usual_distance_km': self.usual_distance_km,
            'training_goal': self.training_goal,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


@dataclass
class Announcement:
    id: int
    title: str
    body: str
    status: str
    is_pinned: bool
    created_at: datetime | None = None

    def model_dump(self, mode: str = 'python'):
        payload = {'id': self.id, 'title': self.title, 'body': self.body, 'status': self.status, 'is_pinned': self.is_pinned}
        if self.created_at is not None:
            payload['created_at'] = self.created_at.isoformat()
        return payload


@dataclass
class Activity:
    id: int
    title: str
    start_time: datetime
    location: str
    route: Optional[str]
    distance_km: Optional[float]
    pace_group: Optional[str]
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    def model_dump(self, mode: str = 'python'):
        return {
            'id': self.id,
            'title': self.title,
            'start_time': self.start_time.isoformat(),
            'location': self.location,
            'route': self.route,
            'distance_km': self.distance_km,
            'pace_group': self.pace_group,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


@dataclass
class Registration:
    id: int
    activity_id: int
    member_id: int
    status: str
    created_at: datetime

    def model_dump(self, mode: str = 'python'):
        return {
            'id': self.id,
            'activity_id': self.activity_id,
            'member_id': self.member_id,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
        }


@dataclass
class Attendance:
    id: int
    activity_id: int
    member_id: int
    status: str
    signed_in_at: datetime
    gps_checked: bool

    def model_dump(self, mode: str = 'python'):
        return {
            'id': self.id,
            'activity_id': self.activity_id,
            'member_id': self.member_id,
            'status': self.status,
            'signed_in_at': self.signed_in_at.isoformat(),
            'gps_checked': self.gps_checked,
        }


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _row_to_member(row) -> Member:
    return Member(
        id=row['id'],
        name=row['name'],
        phone=row['phone'],
        role=row['role'],
        running_years=row['running_years'],
        pace=row['pace'],
        usual_distance_km=row['usual_distance_km'],
        training_goal=row['training_goal'],
        created_at=_parse_dt(row['created_at']),
        updated_at=_parse_dt(row['updated_at']),
    )


def _row_to_announcement(row) -> Announcement:
    return Announcement(
        id=row['id'],
        title=row['title'],
        body=row['body'],
        status=row['status'],
        is_pinned=bool(row['is_pinned']),
        created_at=_parse_dt(row['created_at']),
    )


def _row_to_activity(row) -> Activity:
    return Activity(
        id=row['id'],
        title=row['title'],
        start_time=_parse_dt(row['start_time']),
        location=row['location'],
        route=row['route'],
        distance_km=row['distance_km'],
        pace_group=row['pace_group'],
        description=row['description'],
        created_at=_parse_dt(row['created_at']),
        updated_at=_parse_dt(row['updated_at']),
    )


def _row_to_registration(row) -> Registration:
    return Registration(
        id=row['id'],
        activity_id=row['activity_id'],
        member_id=row['member_id'],
        status=row['status'],
        created_at=_parse_dt(row['created_at']),
    )


def _row_to_attendance(row) -> Attendance:
    return Attendance(
        id=row['id'],
        activity_id=row['activity_id'],
        member_id=row['member_id'],
        status=row['status'],
        signed_in_at=_parse_dt(row['signed_in_at']),
        gps_checked=bool(row['gps_checked']),
    )


def create_member(payload: MemberCreate) -> Member:
    initialize_database()
    with connect() as connection:
        cursor = connection.execute(
            '''
            INSERT INTO members (name, phone, role, running_years, pace, usual_distance_km, training_goal)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (payload.name, payload.phone, payload.role, payload.running_years, payload.pace, payload.usual_distance_km, payload.training_goal),
        )
        row = connection.execute('SELECT * FROM members WHERE id = ?', (cursor.lastrowid,)).fetchone()
        return _row_to_member(row)


def create_member_with_password(payload: MemberCreate | dict[str, Any], password_hash: str):
    initialize_database()
    data = payload.model_dump() if hasattr(payload, 'model_dump') else dict(payload)
    with connect() as connection:
        existing = connection.execute('SELECT id FROM members WHERE phone = ?', (data['phone'],)).fetchone() if data.get('phone') else None
        if existing is not None:
            return None, 'conflict'
        cursor = connection.execute(
            '''
            INSERT INTO members (name, phone, role, running_years, pace, usual_distance_km, training_goal, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (data['name'], data.get('phone'), data['role'], data.get('running_years'), data.get('pace'), data.get('usual_distance_km'), data.get('training_goal'), password_hash),
        )
        row = connection.execute('SELECT * FROM members WHERE id = ?', (cursor.lastrowid,)).fetchone()
        return _row_to_member(row), 'created'


def list_members() -> list[Member]:
    initialize_database()
    with connect() as connection:
        rows = connection.execute('SELECT * FROM members ORDER BY id').fetchall()
        return [_row_to_member(row) for row in rows]


def get_member(member_id: int) -> Member | None:
    initialize_database()
    with connect() as connection:
        row = connection.execute('SELECT * FROM members WHERE id = ?', (member_id,)).fetchone()
        return None if row is None else _row_to_member(row)


def update_member(member_id: int, payload: MemberUpdate) -> Member | None:
    initialize_database()
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return get_member(member_id)
    assignments = ', '.join(f"{key} = ?" for key in data)
    params = list(data.values()) + [member_id]
    with connect() as connection:
        cursor = connection.execute(f'UPDATE members SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', params)
        if cursor.rowcount == 0:
            return None
        row = connection.execute('SELECT * FROM members WHERE id = ?', (member_id,)).fetchone()
        return _row_to_member(row)


def delete_member(member_id: int) -> bool:
    initialize_database()
    with connect() as connection:
        connection.execute('DELETE FROM registrations WHERE member_id = ?', (member_id,))
        connection.execute('DELETE FROM attendances WHERE member_id = ?', (member_id,))
        cursor = connection.execute('DELETE FROM members WHERE id = ?', (member_id,))
        return cursor.rowcount > 0


def create_announcement(payload: AnnouncementCreate) -> Announcement:
    initialize_database()
    with connect() as connection:
        cursor = connection.execute(
            '''
            INSERT INTO announcements (title, body, status, is_pinned)
            VALUES (?, ?, ?, ?)
            ''',
            (payload.title, payload.body, payload.status, int(payload.is_pinned)),
        )
        row = connection.execute('SELECT * FROM announcements WHERE id = ?', (cursor.lastrowid,)).fetchone()
        return _row_to_announcement(row)


def list_announcements() -> list[Announcement]:
    initialize_database()
    with connect() as connection:
        rows = connection.execute('SELECT * FROM announcements ORDER BY is_pinned DESC, created_at DESC, id DESC').fetchall()
        return [_row_to_announcement(row) for row in rows]


def get_announcement(announcement_id: int) -> Announcement | None:
    initialize_database()
    with connect() as connection:
        row = connection.execute('SELECT * FROM announcements WHERE id = ?', (announcement_id,)).fetchone()
        return None if row is None else _row_to_announcement(row)


def update_announcement(announcement_id: int, payload: AnnouncementUpdate) -> Announcement | None:
    initialize_database()
    data = payload.model_dump(exclude_unset=True)
    if 'content' in data and 'body' not in data:
        data['body'] = data.pop('content')
    if not data:
        return get_announcement(announcement_id)
    assignments = ', '.join(f"{key} = ?" for key in data)
    params = list(data.values()) + [announcement_id]
    with connect() as connection:
        cursor = connection.execute(f'UPDATE announcements SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', params)
        if cursor.rowcount == 0:
            return None
        row = connection.execute('SELECT * FROM announcements WHERE id = ?', (announcement_id,)).fetchone()
        return _row_to_announcement(row)


def delete_announcement(announcement_id: int) -> bool:
    initialize_database()
    with connect() as connection:
        cursor = connection.execute('DELETE FROM announcements WHERE id = ?', (announcement_id,))
        return cursor.rowcount > 0


def create_activity(payload: ActivityCreate):
    initialize_database()
    with connect() as connection:
        cursor = connection.execute(
            '''
            INSERT INTO activities (title, start_time, location, route, distance_km, pace_group, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (payload.title, payload.start_time.isoformat(), payload.location, payload.route, payload.distance_km, payload.pace_group, payload.description),
        )
        row = connection.execute('SELECT * FROM activities WHERE id = ?', (cursor.lastrowid,)).fetchone()
        return _row_to_activity(row)


def list_activities():
    initialize_database()
    with connect() as connection:
        rows = connection.execute('SELECT * FROM activities ORDER BY start_time DESC, id DESC').fetchall()
        return [_row_to_activity(row) for row in rows]


def get_activity(activity_id: int):
    initialize_database()
    with connect() as connection:
        row = connection.execute('SELECT * FROM activities WHERE id = ?', (activity_id,)).fetchone()
        return None if row is None else _row_to_activity(row)


def update_activity(activity_id: int, payload: ActivityUpdate):
    initialize_database()
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return get_activity(activity_id)
    if 'start_time' in data and data['start_time'] is not None:
        data['start_time'] = data['start_time'].isoformat()
    assignments = ', '.join(f"{key} = ?" for key in data)
    params = list(data.values()) + [activity_id]
    with connect() as connection:
        cursor = connection.execute(f'UPDATE activities SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', params)
        if cursor.rowcount == 0:
            return None
        row = connection.execute('SELECT * FROM activities WHERE id = ?', (activity_id,)).fetchone()
        return _row_to_activity(row)


def delete_activity(activity_id: int) -> bool:
    initialize_database()
    with connect() as connection:
        connection.execute('DELETE FROM registrations WHERE activity_id = ?', (activity_id,))
        connection.execute('DELETE FROM attendances WHERE activity_id = ?', (activity_id,))
        cursor = connection.execute('DELETE FROM activities WHERE id = ?', (activity_id,))
        return cursor.rowcount > 0


def create_registration(activity_id: int, member_id: int):
    initialize_database()
    with connect() as connection:
        activity = connection.execute('SELECT id FROM activities WHERE id = ?', (activity_id,)).fetchone()
        member = connection.execute('SELECT id FROM members WHERE id = ?', (member_id,)).fetchone()
        if activity is None or member is None:
            return None, 'not_found'
        existing = connection.execute('SELECT * FROM registrations WHERE activity_id = ? AND member_id = ?', (activity_id, member_id)).fetchone()
        if existing is not None and existing['status'] == 'registered':
            return _row_to_registration(existing), 'conflict'
        if existing is not None:
            connection.execute('UPDATE registrations SET status = ?, created_at = CURRENT_TIMESTAMP WHERE id = ?', ('registered', existing['id']))
            row = connection.execute('SELECT * FROM registrations WHERE id = ?', (existing['id'],)).fetchone()
            return _row_to_registration(row), 'updated'
        cursor = connection.execute('INSERT INTO registrations (activity_id, member_id, status) VALUES (?, ?, ?)', (activity_id, member_id, 'registered'))
        row = connection.execute('SELECT * FROM registrations WHERE id = ?', (cursor.lastrowid,)).fetchone()
        return _row_to_registration(row), 'created'


def cancel_registration(activity_id: int, member_id: int):
    initialize_database()
    with connect() as connection:
        existing = connection.execute('SELECT * FROM registrations WHERE activity_id = ? AND member_id = ?', (activity_id, member_id)).fetchone()
        if existing is None:
            return None
        connection.execute('UPDATE registrations SET status = ?, created_at = CURRENT_TIMESTAMP WHERE id = ?', ('cancelled', existing['id']))
        row = connection.execute('SELECT * FROM registrations WHERE id = ?', (existing['id'],)).fetchone()
        return _row_to_registration(row)


def create_attendance(activity_id: int, member_id: int, gps_checked: bool = False, checked_in_at: datetime | None = None):
    initialize_database()
    signed_in_at = checked_in_at or datetime.now(timezone.utc)
    if signed_in_at.tzinfo is None:
        signed_in_at = signed_in_at.replace(tzinfo=timezone.utc)
    with connect() as connection:
        activity = connection.execute('SELECT id FROM activities WHERE id = ?', (activity_id,)).fetchone()
        member = connection.execute('SELECT id FROM members WHERE id = ?', (member_id,)).fetchone()
        if activity is None or member is None:
            return None, 'not_found'
        registration = connection.execute('SELECT status FROM registrations WHERE activity_id = ? AND member_id = ?', (activity_id, member_id)).fetchone()
        if registration is None or registration['status'] != 'registered':
            return None, 'not_registered'
        existing = connection.execute('SELECT * FROM attendances WHERE activity_id = ? AND member_id = ?', (activity_id, member_id)).fetchone()
        if existing is not None:
            connection.execute('UPDATE attendances SET status = ?, signed_in_at = ?, gps_checked = ? WHERE id = ?', ('signed_in', signed_in_at.isoformat(), int(gps_checked), existing['id']))
            row = connection.execute('SELECT * FROM attendances WHERE id = ?', (existing['id'],)).fetchone()
            return _row_to_attendance(row), 'updated'
        cursor = connection.execute('INSERT INTO attendances (activity_id, member_id, status, signed_in_at, gps_checked) VALUES (?, ?, ?, ?, ?)', (activity_id, member_id, 'signed_in', signed_in_at.isoformat(), int(gps_checked)))
        row = connection.execute('SELECT * FROM attendances WHERE id = ?', (cursor.lastrowid,)).fetchone()
        return _row_to_attendance(row), 'created'


def list_attendance(activity_id: int):
    initialize_database()
    with connect() as connection:
        rows = connection.execute('SELECT * FROM attendances WHERE activity_id = ? ORDER BY id DESC', (activity_id,)).fetchall()
        return [_row_to_attendance(row) for row in rows]


def delete_attendance(attendance_id: int) -> bool:
    initialize_database()
    with connect() as connection:
        cursor = connection.execute('DELETE FROM attendances WHERE id = ?', (attendance_id,))
        return cursor.rowcount > 0


def get_attendance(attendance_id: int):
    initialize_database()
    with connect() as connection:
        row = connection.execute('SELECT * FROM attendances WHERE id = ?', (attendance_id,)).fetchone()
        return None if row is None else _row_to_attendance(row)


def create_task_queue_worker(worker_key: str, name: str, status: str, capabilities: list[str]):
    initialize_database()
    capabilities_value = str(capabilities).replace("'", '"')
    with connect() as connection:
        existing = connection.execute('SELECT * FROM task_queue_workers WHERE worker_key = ?', (worker_key,)).fetchone()
        if existing is not None:
            connection.execute(
                'UPDATE task_queue_workers SET name = ?, status = ?, capabilities = ?, last_seen_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE worker_key = ?',
                (name, status, capabilities_value, worker_key),
            )
            row = connection.execute('SELECT * FROM task_queue_workers WHERE worker_key = ?', (worker_key,)).fetchone()
            return dict(row), 'updated'
        cursor = connection.execute(
            'INSERT INTO task_queue_workers (worker_key, name, status, capabilities) VALUES (?, ?, ?, ?)',
            (worker_key, name, status, capabilities_value),
        )
        row = connection.execute('SELECT * FROM task_queue_workers WHERE id = ?', (cursor.lastrowid,)).fetchone()
        return dict(row), 'created'


def ensure_workspace_tasks_table() -> None:
    initialize_database()
    with connect() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS workspace_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace TEXT NOT NULL,
                task_key TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('todo', 'ready', 'running', 'blocked', 'done', 'archived')),
                assignee TEXT,
                priority INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT NOT NULL DEFAULT '{}',
                UNIQUE(workspace, task_key)
            )
            '''
        )


def list_task_queue_workers() -> list[dict[str, Any]]:
    initialize_database()
    with connect() as connection:
        rows = connection.execute('SELECT * FROM task_queue_workers ORDER BY updated_at DESC, id DESC').fetchall()
        return [dict(row) for row in rows]


def list_activity_attendance(activity_id: int):
    return list_attendance(activity_id)
