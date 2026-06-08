from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status

from ..attendance import list_attendance
from ..repository import get_member
from ..models import ApiResponse

router = APIRouter(prefix='/api/v1', tags=['checkin-stats'])


def _to_date(value: Any) -> date:
    """Convert a database value to a date.

    Args:
        value: Database value that may be a date or datetime string.

    Returns:
        Parsed date.

    Raises:
        ValueError: If the value cannot be parsed.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError('empty date')
        return datetime.fromisoformat(text.replace('Z', '+00:00')).date()
    raise ValueError('unsupported date value')


    records = list_attendance(member_id)
    dates: list[date] = []
    for record in records:
        if getattr(record, 'status', '') != 'signed_in':
            continue
        signed_at = getattr(record, 'signed_in_at', None)
        if signed_at is None:
            continue
        try:
            dates.append(_to_date(signed_at))
        except ValueError:
            continue
    dates.sort()
    return dates


def _continuous_days(dates: list[date]) -> tuple[int, int]:
    """Compute current and longest consecutive check-in streaks.

    Args:
        dates: Sorted signed-in dates.

    Returns:
        Current streak and longest streak.
    """
    if not dates:
        return 0, 0
    unique_dates = sorted(set(dates))
    longest = 1
    current = 1
    prev = unique_dates[0]
    for current_date in unique_dates[1:]:
        if (current_date - prev).days == 1:
            current += 1
        else:
            current = 1
        longest = max(longest, current)
        prev = current_date
    today = date.today()
    streak = 0
    expected = today
    for current_date in reversed(unique_dates):
        if current_date == expected:
            streak += 1
            expected = expected.fromordinal(expected.toordinal() - 1)
            continue
        if current_date < expected:
            break
    return streak, longest


def _monthly_days(dates: list[date]) -> int:
    """Count signed-in days in the current month.

    Args:
        dates: Signed-in dates.

    Returns:
        Distinct signed-in days in current month.
    """
    today = date.today()
    return len({item for item in dates if item.year == today.year and item.month == today.month})


@router.get('/checkin-stats/{member_id}', response_model=ApiResponse)
def get_checkin_stats(member_id: int) -> ApiResponse:
    """Return member check-in statistics.

    Args:
        member_id: Member identifier.

    Returns:
        ApiResponse with streak, longest streak, month count, and recent dates.

    Raises:
        HTTPException: When the member does not exist.
    """
    if member_id <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='成员ID必须大于 0')
    member = get_member(member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='成员不存在')
    dates = _fetch_checkin_dates(member_id)
    current_streak, longest_streak = _continuous_days(dates)
    today = date.today()
    recent_dates = [item.isoformat() for item in dates if (today - item).days <= 365]
    recent_dates = recent_dates[-365:]
    payload = {
        'member_id': member_id,
        'current_streak_days': current_streak,
        'longest_streak_days': longest_streak,
        'checkin_days_this_month': _monthly_days(dates),
        'recent_checkin_dates': recent_dates,
    }
    return ApiResponse(data=payload, message='签到统计获取成功')


@router.get('/checkin-heatmap/{member_id}', response_model=ApiResponse)
def get_checkin_heatmap(member_id: int) -> ApiResponse:
    """Return member check-in heatmap data.

    Args:
        member_id: Member identifier.

    Returns:
        ApiResponse with daily counts for the last year.

    Raises:
        HTTPException: When the member does not exist.
    """
    if member_id <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='成员ID必须大于 0')
    member = get_member(member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='成员不存在')
    dates = _fetch_checkin_dates(member_id)
    cutoff = date.today().fromordinal(date.today().toordinal() - 365)
    grouped: dict[str, int] = {}
    for current_date in dates:
        if current_date < cutoff:
            continue
        key = current_date.isoformat()
        grouped[key] = grouped.get(key, 0) + 1
    items = [{'date': key, 'count': grouped[key]} for key in sorted(grouped)]
    return ApiResponse(data=items, message='热力图数据获取成功')
