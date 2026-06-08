from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status

from ..database import DB_PATH
from ..models import ApiResponse

router = APIRouter(prefix='/api/v1', tags=['checkin-stats'])


def _resolve_db_path() -> Path:
    """Resolve the active 查询语句ite database path.

    Returns:
        Resolved database path.
    """
    return Path(DB_PATH)


def _connect() -> sqlite3.Connection:
    """Open a 查询语句ite connection with row factory enabled.

    Returns:
        查询语句ite connection.
    """
    connection = sqlite3.connect(str(_resolve_db_path()))
    connection.row_factory = sqlite3.Row
    return connection


def _member_exists(member_id: int) -> bool:
    """Check whether a member exists.

    Args:
        member_id: Member identifier.

    Returns:
        True when the member exists.
    """
    with _connect() as connection:
        row = connection.execute('SELECT 1 FROM members WHERE id = ?', (member_id,)).fetchone()
    return row is not None


def _fetch_attendance_rows(member_id: int) -> list[sqlite3.Row]:
    """Fetch all attendance rows for a member.

    Args:
        member_id: Member identifier.

    Returns:
        Attendance rows ordered by signed-in timestamp.
    """
    with _connect() as connection:
        rows = connection.execute(
            '''
            SELECT activity_id, member_id, signed_in_at, status
            FROM attendances
            WHERE member_id = ?
            ORDER BY signed_in_at ASC, id ASC
            ''',
            (member_id,),
        ).fetchall()
    return list(rows)


def _signed_in_dates(member_id: int) -> list[date]:
    """Collect deduplicated signed-in dates for a member.

    Args:
        member_id: Member identifier.

    Returns:
        List of signed-in dates in ascending order.
    """
    dates: list[date] = []
    seen: set[date] = set()
    for row in _fetch_attendance_rows(member_id):
        if row['status'] != 'signed_in' or not row['signed_in_at']:
            continue
        signed_in_at = datetime.fromisoformat(str(row['signed_in_at']).replace('Z', '+00:00'))
        current_date = signed_in_at.date()
        if current_date not in seen:
            seen.add(current_date)
            dates.append(current_date)
    return dates


def _month_range(reference: date) -> tuple[date, date]:
    """Build the inclusive month range for a reference date.

    Args:
        reference: Reference date.

    Returns:
        Start and end dates for the current month.
    """
    start = reference.replace(day=1)
    if start.month == 12:
        end = date(start.year, 12, 31)
    else:
        next_month = date(start.year + (1 if start.month == 12 else 0), 1 if start.month == 12 else start.month + 1, 1)
        end = next_month - timedelta(days=1)
    return start, end


def _last_365_days(reference: date) -> list[date]:
    """Build a 365-day window ending on the reference date.

    Args:
        reference: Reference date.

    Returns:
        List of dates from the last 365 days.
    """
    start = reference - timedelta(days=364)
    return [start + timedelta(days=offset) for offset in range(365)]


def _streak_and_longest(dates: list[date]) -> tuple[int, int]:
    """Compute current and longest signing streaks.

    Args:
        dates: Deduplicated signed-in dates.

    Returns:
        Current streak and longest streak.
    """
    if not dates:
        return 0, 0
    unique_dates = sorted(set(dates))
    longest = 1
    streak = 1
    for previous, current_date in zip(unique_dates, unique_dates[1:]):
        if current_date == previous + timedelta(days=1):
            streak += 1
        else:
            longest = max(longest, streak)
            streak = 1
    longest = max(longest, streak)
    current = 1
    for previous, current_date in zip(reversed(unique_dates[:-1]), reversed(unique_dates[1:])):
        if previous + timedelta(days=1) == current_date:
            current += 1
        else:
            break
    return current, longest


def _build_heatmap(member_id: int) -> list[dict[str, Any]]:
    """Build 365-day heatmap data for a member.

    Args:
        member_id: Member identifier.

    Returns:
        Heatmap rows with date and count.
    """
    reference = datetime.now(timezone.utc).date()
    days = _last_365_days(reference)
    counts = {day: 0 for day in days}
    for row in _fetch_attendance_rows(member_id):
        if row['status'] != 'signed_in' or not row['signed_in_at']:
            continue
        signed_in_at = datetime.fromisoformat(str(row['signed_in_at']).replace('Z', '+00:00'))
        current_date = signed_in_at.date()
        if current_date in counts:
            counts[current_date] += 1
    return [{'date': day.isoformat(), 'count': counts[day]} for day in days]


@router.get('/checkin-stats/{member_id}', response_model=ApiResponse)
def read_checkin_stats(member_id: int) -> ApiResponse:
    """Return sign-in statistics for a member.

    Args:
        member_id: Member identifier.

    Returns:
        ApiResponse with streak and date data.

    Raises:
        HTTPException: When the member does not exist.
    """
    if not _member_exists(member_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='成员不存在')
    dates = _signed_in_dates(member_id)
    current_streak, longest_streak = _streak_and_longest(dates)
    reference = datetime.now(timezone.utc).date()
    month_start, month_end = _month_range(reference)
    month_checkins = sum(1 for day in dates if month_start <= day <= month_end)
    return ApiResponse(
        data={
            'member_id': member_id,
            'current_streak_days': current_streak,
            'longest_streak_days': longest_streak,
            'month_checkin_days': month_checkins,
            'checkin_dates': [day.isoformat() for day in dates],
        }
    )


@router.get('/checkin-heatmap/{member_id}', response_model=ApiResponse)
def read_checkin_heatmap(member_id: int) -> ApiResponse:
    """Return 365-day check-in heatmap data for a member.

    Args:
        member_id: Member identifier.

    Returns:
        ApiResponse with date/count rows.

    Raises:
        HTTPException: When the member does not exist.
    """
    if not _member_exists(member_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='成员不存在')
    return ApiResponse(data=_build_heatmap(member_id))
