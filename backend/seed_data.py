from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
import json


@dataclass(frozen=True)
class SeedPack:
    members: list[dict[str, object]]
    activities: list[dict[str, object]]
    registrations: list[dict[str, object]]
    attendances: list[dict[str, object]]
    announcements: list[dict[str, object]]


_BASE_TIME = datetime(2026, 6, 1, 6, 0, tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


def build_seed_pack() -> SeedPack:
    members = [
        {
            'name': 'Li Ming',
            'phone': '15550010001',
            'role': 'leader',
            'running_years': 8,
            'pace': '5:10/km',
            'usual_distance_km': 12.0,
            'training_goal': 'Lead the Tuesday tempo group',
            'password_hash': 'seeded-password-hash-leader',
        },
        {
            'name': 'Chen Yu',
            'phone': '15550010002',
            'role': 'admin',
            'running_years': 5,
            'pace': '5:45/km',
            'usual_distance_km': 10.0,
            'training_goal': 'Keep the member directory tidy',
            'password_hash': 'seeded-password-hash-admin',
        },
        {
            'name': 'Wang Fang',
            'phone': '15550010003',
            'role': 'member',
            'running_years': 2,
            'pace': '6:20/km',
            'usual_distance_km': 8.0,
            'training_goal': 'Finish a 10K in under 65 minutes',
            'password_hash': 'seeded-password-hash-member-a',
        },
        {
            'name': 'Zhao Lei',
            'phone': '15550010004',
            'role': 'member',
            'running_years': 1,
            'pace': '6:50/km',
            'usual_distance_km': 6.0,
            'training_goal': 'Build consistency with easy runs',
            'password_hash': 'seeded-password-hash-member-b',
        },
    ]

    activities = [
        {
            'title': 'Tuesday Track Tempo',
            'start_time': _iso(_BASE_TIME + timedelta(days=1, hours=1)),
            'location': 'City Stadium Track',
            'route': '8 x 400m intervals',
            'distance_km': 9.6,
            'pace_group': 'tempo',
            'description': 'Warm up together, then run controlled repeats with full recovery.',
        },
        {
            'title': 'Weekend Long Run',
            'start_time': _iso(_BASE_TIME + timedelta(days=4, hours=2)),
            'location': 'Riverside Park',
            'route': 'Out-and-back loop',
            'distance_km': 16.0,
            'pace_group': 'easy',
            'description': 'A social long run with two hydration stops and a cooldown coffee.',
        },
        {
            'title': 'Strength and Mobility Night',
            'start_time': _iso(_BASE_TIME + timedelta(days=2, hours=3)),
            'location': 'Club House',
            'route': None,
            'distance_km': None,
            'pace_group': 'recovery',
            'description': 'Core work, hip mobility, and light strides for recovery.',
        },
    ]

    registrations = [
        {'activity_index': 0, 'member_index': 0, 'status': 'registered'},
        {'activity_index': 0, 'member_index': 2, 'status': 'registered'},
        {'activity_index': 1, 'member_index': 0, 'status': 'registered'},
        {'activity_index': 1, 'member_index': 2, 'status': 'registered'},
        {'activity_index': 1, 'member_index': 3, 'status': 'cancelled'},
        {'activity_index': 2, 'member_index': 1, 'status': 'registered'},
    ]

    attendances = [
        {'activity_index': 0, 'member_index': 0, 'status': 'signed_in', 'signed_in_at': _iso(_BASE_TIME + timedelta(days=1, minutes=12)), 'gps_checked': 1},
        {'activity_index': 0, 'member_index': 2, 'status': 'signed_in', 'signed_in_at': _iso(_BASE_TIME + timedelta(days=1, minutes=17)), 'gps_checked': 0},
        {'activity_index': 1, 'member_index': 0, 'status': 'signed_in', 'signed_in_at': _iso(_BASE_TIME + timedelta(days=4, minutes=5)), 'gps_checked': 1},
        {'activity_index': 2, 'member_index': 1, 'status': 'absent', 'signed_in_at': _iso(_BASE_TIME + timedelta(days=2, minutes=30)), 'gps_checked': 0},
    ]

    announcements = [
        {
            'title': 'Weekly training plan published',
            'body': 'The Tuesday tempo, Thursday mobility session, and weekend long run are now on the calendar.',
            'status': 'published',
            'is_pinned': 1,
        },
        {
            'title': 'Bring your own hydration belt',
            'body': 'Please bring a hydration belt or bottle for the longer weekend long run.',
            'status': 'published',
            'is_pinned': 0,
        },
    ]

    return SeedPack(members, activities, registrations, attendances, announcements)


def export_seed_pack(target_path: str | Path) -> Path:
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    pack = build_seed_pack()
    payload = {
        'members': pack.members,
        'activities': pack.activities,
        'registrations': pack.registrations,
        'attendances': pack.attendances,
        'announcements': pack.announcements,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return target


def iter_seed_rows() -> Iterable[tuple[str, dict[str, object]]]:
    pack = build_seed_pack()
    for row in pack.members:
        yield 'members', row
    for row in pack.activities:
        yield 'activities', row
    for row in pack.registrations:
        yield 'registrations', row
    for row in pack.attendances:
        yield 'attendances', row
    for row in pack.announcements:
        yield 'announcements', row
