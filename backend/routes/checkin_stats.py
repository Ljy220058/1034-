from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status

from ..database import connect
from ..models import ApiResponse

router = APIRouter(prefix='/api/v1', tags=['checkin-stats'])


def _member_exists(member_id: int) -> bool:
    """检查成员是否存在。

    Args:
        member_id: 成员 ID。

    Returns:
        成员存在时返回 True。
    """
    with connect() as connection:
        row = connection.execute('SELECT 1 FROM members WHERE id = ?', (member_id,)).fetchone()
    return row is not None



def _fetch_attendance_rows(member_id: int) -> list[tuple[str, int]]:
    """读取成员近年打卡数据。

    Args:
        member_id: 成员 ID。

    Returns:
        以日期字符串和打卡次数构成的行列表。
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=365)).date().isoformat()
    with connect() as connection:
        rows = connection.execute(
            '''
            SELECT DATE(COALESCE(signed_in_at, created_at)) AS checkin_date, COUNT(*) AS count
            FROM attendances
            WHERE member_id = ?
              AND status = 'signed_in'
              AND DATE(COALESCE(signed_in_at, created_at)) >= ?
            GROUP BY checkin_date
            ORDER BY checkin_date ASC
            ''',
            (member_id, cutoff),
        ).fetchall()
    return [(str(row['checkin_date']), int(row['count'])) for row in rows]



def _build_daily_map(rows: list[tuple[str, int]]) -> dict[str, int]:
    """把打卡行转换为日期计数映射。"""
    return {checkin_date: count for checkin_date, count in rows}



def _count_month_checkins(rows: list[tuple[str, int]]) -> int:
    """统计本月打卡天数。"""
    today = date.today()
    month_key = f'{today.year:04d}-{today.month:02d}'
    return sum(1 for checkin_date, _ in rows if checkin_date.startswith(month_key))



def _longest_streak(rows: list[tuple[str, int]]) -> int:
    """计算历史最长连续打卡天数。"""
    days = sorted({datetime.fromisoformat(checkin_date).date() for checkin_date, count in rows if count > 0})
    if not days:
        return 0
    longest = current = 1
    for index in range(1, len(days)):
        if days[index] == days[index - 1] + timedelta(days=1):
            current += 1
        else:
            longest = max(longest, current)
            current = 1
    return max(longest, current)



def _current_streak(rows: list[tuple[str, int]]) -> int:
    """计算当前连续打卡天数。"""
    dates = {datetime.fromisoformat(checkin_date).date() for checkin_date, count in rows if count > 0}
    if not dates:
        return 0
    streak = 0
    cursor = date.today()
    while cursor in dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak



def _last_365_dates(rows: list[tuple[str, int]]) -> list[dict[str, Any]]:
    """返回最近 365 天的热力图日期列表。"""
    counter: Counter[str] = Counter()
    for checkin_date, count in rows:
        counter[checkin_date] += count
    start = date.today() - timedelta(days=364)
    dates: list[dict[str, Any]] = []
    for offset in range(365):
        current = start + timedelta(days=offset)
        key = current.isoformat()
        dates.append({'date': key, 'count': counter.get(key, 0)})
    return dates


@router.get('/checkin-stats/{member_id}', response_model=ApiResponse)
def read_checkin_stats(member_id: int) -> ApiResponse:
    """获取成员打卡统计。

    Args:
        member_id: 成员 ID。

    Returns:
        包含连续打卡、本月打卡和近 365 天打卡日期列表的统计结果。

    Raises:
        HTTPException: 成员不存在时返回 404。
    """
    if not _member_exists(member_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='成员不存在')

    rows = _fetch_attendance_rows(member_id)
    stats = {
        'member_id': member_id,
        'current_streak_days': _current_streak(rows),
        'longest_streak_days': _longest_streak(rows),
        'checkin_days_this_month': _count_month_checkins(rows),
        'recent_365_days': [item['date'] for item in _last_365_dates(rows) if item['count'] > 0],
    }
    return ApiResponse(data=stats, message='打卡统计获取成功')


@router.get('/checkin-heatmap/{member_id}', response_model=ApiResponse)
def read_checkin_heatmap(member_id: int) -> ApiResponse:
    """获取成员近一年热力图数据。

    Args:
        member_id: 成员 ID。

    Returns:
        近 365 天按日期聚合的打卡次数。

    Raises:
        HTTPException: 成员不存在时返回 404。
    """
    if not _member_exists(member_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='成员不存在')

    rows = _fetch_attendance_rows(member_id)
    return ApiResponse(data=_last_365_dates(rows), message='打卡热力图获取成功')
