from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, status

from .. import database
from ..models import ApiResponse

router = APIRouter(prefix='/api/v1/members', tags=['member-insights'])


def _parse_datetime(value: str) -> datetime:
    """解析 查询语句ite 中的时间文本。

    Args:
        value: 时间文本。

    Returns:
        解析后的 datetime 对象。
    """
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def _parse_date(value: str) -> date:
    """解析 查询语句ite 日期文本。

    Args:
        value: 日期文本。

    Returns:
        日期对象。
    """
    try:
        return _parse_datetime(value).date()
    except ValueError:
        return date.fromisoformat(value)


def _member_exists(member_id: int) -> bool:
    """检查成员是否存在。

    Args:
        member_id: 成员 ID。

    Returns:
        成员存在则返回 True。
    """
    with database.connect() as connection:
        row = connection.execute('SELECT 1 FROM members WHERE id = ?', (member_id,)).fetchone()
    return row is not None


def _fetch_member_activities(member_id: int, year: int | None = None) -> list[sqlite3.Row]:
    """读取成员参与的活动与签到信息。

    Args:
        member_id: 成员 ID。
        year: 可选年份过滤。

    Returns:
        查询结果行列表。
    """
    query = [
        'SELECT',
        '    a.id AS activity_id,',
        '    a.title,',
        '    a.start_time,',
        '    a.distance_km,',
        '    att.signed_in_at,',
        '    att.status AS attendance_status',
        'FROM attendances att',
        'JOIN activities a ON a.id = att.activity_id',
        'WHERE att.member_id = ? AND att.status = \'signed_in\'',
    ]
    params: list[Any] = [member_id]
    if year is not None:
        query.append('AND strftime(\'%Y\', a.start_time) = ?')
        params.append(f'{year:04d}')
    query.append('ORDER BY a.start_time ASC, a.id ASC')
    with database.connect() as connection:
        rows = connection.execute('\n'.join(query), params).fetchall()
    return list(rows)


def _current_streak_days(rows: list[sqlite3.Row]) -> int:
    """计算当前连续打卡天数。

    Args:
        rows: 签到记录。

    Returns:
        连续天数。
    """
    if not rows:
        return 0
    sign_in_dates = sorted({ _parse_date(str(row['signed_in_at'])) for row in rows })
    date_set = set(sign_in_dates)
    streak = 0
    cursor = date.today()
    while cursor in date_set:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _longest_streak_days(rows: list[sqlite3.Row]) -> int:
    """计算历史最长连续打卡天数。

    Args:
        rows: 签到记录。

    Returns:
        最长连续天数。
    """
    if not rows:
        return 0
    sign_in_dates = sorted({ _parse_date(str(row['signed_in_at'])) for row in rows })
    longest = 0
    running = 0
    previous_day: date | None = None
    for current_day in sign_in_dates:
        if previous_day is not None and current_day == previous_day + timedelta(days=1):
            running += 1
        else:
            running = 1
        longest = max(longest, running)
        previous_day = current_day
    return longest


def _stats_summary_payload(member_id: int, rows: list[sqlite3.Row]) -> dict[str, Any]:
    """构建成员统计摘要。

    Args:
        member_id: 成员 ID。
        rows: 签到记录。

    Returns:
        ApiResponse 的 data 内容。
    """
    unique_dates = sorted({ _parse_date(str(row['signed_in_at'])) for row in rows })
    total_activities = len(unique_dates)
    total_distance_km = round(sum(float(row['distance_km'] or 0) for row in rows), 2)
    monthly_counts: dict[str, int] = defaultdict(int)
    for current_day in unique_dates:
        monthly_counts[current_day.strftime('%Y-%m')] += 1
    best_month = None
    if monthly_counts:
        best_month = max(monthly_counts.items(), key=lambda item: (item[1], item[0]))[0]
    return {
        'member_id': member_id,
        'total_distance_km': total_distance_km,
        'total_activities': total_activities,
        'current_streak_days': _current_streak_days(rows),
        'best_streak_days': _longest_streak_days(rows),
        'best_month': best_month,
    }


def _timeline_payload(member_id: int, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """构建按月分组的时间线数据。

    Args:
        member_id: 成员 ID。
        rows: 签到记录。

    Returns:
        按月归档的活动列表。
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        signed_in_at = _parse_datetime(str(row['signed_in_at']))
        month_key = signed_in_at.strftime('%Y-%m')
        cover_image = ''
        grouped[month_key].append(
            {
                'date': signed_in_at.date().isoformat(),
                'activity_id': row['activity_id'],
                'title': row['title'],
                'distance_km': float(row['distance_km'] or 0),
                'pace_min_per_km': None,
                'photo_thumbnail': cover_image,
            }
        )
    return [
        {'month': month, 'activities': items}
        for month, items in sorted(grouped.items())
    ]


@router.get('/{member_id}/stats-summary', response_model=ApiResponse)
def read_member_stats_summary(member_id: int) -> ApiResponse:
    """获取成员统计摘要。

    Args:
        member_id: 成员 ID。

    Returns:
        ApiResponse 包裹的统计摘要。

    Raises:
        HTTPException: 成员不存在时返回 404。
    """
    if not _member_exists(member_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='成员不存在')
    rows = _fetch_member_activities(member_id)
    return ApiResponse(data=_stats_summary_payload(member_id, rows))


@router.get('/{member_id}/timeline', response_model=ApiResponse)
def read_member_timeline(member_id: int, year: int | None = None) -> ApiResponse:
    """获取成员时间线。

    Args:
        member_id: 成员 ID。
        year: 可选年份过滤。

    Returns:
        ApiResponse 包裹的按月活动列表。

    Raises:
        HTTPException: 成员不存在时返回 404。
    """
    if not _member_exists(member_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='成员不存在')
    rows = _fetch_member_activities(member_id, year=year)
    return ApiResponse(data=_timeline_payload(member_id, rows))
