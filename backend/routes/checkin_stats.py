from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status

from .. import database
from ..models import ApiResponse

router = APIRouter(prefix='/api/v1', tags=['checkin-stats'])


def _parse_date(value: str) -> date:
    """解析 查询语句ite 日期文本。

    Args:
        value: 查询语句ite 中的日期或日期时间文本。

    Returns:
        归一化后的日期对象。

    Raises:
        ValueError: 日期无法解析时抛出。
    """
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).date()
    except ValueError:
        return date.fromisoformat(value)


def _attendance_rows(member_id: int) -> list[sqlite3.Row]:
    """读取成员的已签到记录。

    Args:
        member_id: 成员 ID。

    Returns:
        已签到 attendance 行列表。
    """
    with database.connect() as connection:
        rows = connection.execute(
            '''
            SELECT signed_in_at
            FROM attendances
            WHERE member_id = ? AND status = 'signed_in'
            ORDER BY signed_in_at ASC, id ASC
            ''',
            (member_id,),
        ).fetchall()
    return list(rows)


def _build_stat_payload(member_id: int, rows: list[sqlite3.Row]) -> dict[str, Any]:
    """构建签到统计响应。

    Args:
        member_id: 成员 ID。
        rows: 已签到记录。

    Returns:
        可序列化的统计数据。
    """
    sign_in_dates = [_parse_date(str(row['signed_in_at'])) for row in rows]
    if not sign_in_dates:
        return {
            'member_id': member_id,
            'current_streak_days': 0,
            'longest_streak_days': 0,
            'month_checkin_days': 0,
            'checkin_dates': [],
        }

    unique_dates = sorted(set(sign_in_dates))
    date_set = set(unique_dates)
    current_streak = 0
    cursor = date.today()
    while cursor in date_set:
        current_streak += 1
        cursor -= timedelta(days=1)

    longest_streak = 0
    running = 0
    previous_day: date | None = None
    for current_day in unique_dates:
        if previous_day is not None and current_day == previous_day + timedelta(days=1):
            running += 1
        else:
            running = 1
        longest_streak = max(longest_streak, running)
        previous_day = current_day

    current_month = date.today().replace(day=1)
    next_month = (current_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_checkins = sum(1 for value in sign_in_dates if current_month <= value < next_month)
    recent_dates = [day.isoformat() for day in unique_dates if day >= date.today() - timedelta(days=364)]

    return {
        'member_id': member_id,
        'current_streak_days': current_streak,
        'longest_streak_days': longest_streak,
        'month_checkin_days': month_checkins,
        'checkin_dates': recent_dates,
    }


def _build_heatmap_payload(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """构建近一年热力图数据。

    Args:
        rows: 已签到记录。

    Returns:
        按日期聚合后的热力图数据。
    """
    counts: dict[str, int] = defaultdict(int)
    cutoff = date.today() - timedelta(days=364)
    for row in rows:
        signed_day = _parse_date(str(row['signed_in_at']))
        if signed_day >= cutoff:
            counts[signed_day.isoformat()] += 1
    return [{'date': day, 'count': counts[day]} for day in sorted(counts)]


@router.get('/checkin-stats/{member_id}', response_model=ApiResponse)
def read_checkin_stats(member_id: int) -> ApiResponse:
    """获取成员签到统计。

    Args:
        member_id: 成员 ID。

    Returns:
        ApiResponse 包裹的统计数据。

    Raises:
        HTTPException: 成员不存在时返回 404。
    """
    with database.connect() as connection:
        member_exists = connection.execute('SELECT 1 FROM members WHERE id = ?', (member_id,)).fetchone()
    if member_exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='成员不存在')
    rows = _attendance_rows(member_id)
    return ApiResponse(data=_build_stat_payload(member_id, rows))


@router.get('/checkin-heatmap/{member_id}', response_model=ApiResponse)
def read_checkin_heatmap(member_id: int) -> ApiResponse:
    """获取成员近一年签到热力图数据。

    Args:
        member_id: 成员 ID。

    Returns:
        ApiResponse 包裹的热力图数据。

    Raises:
        HTTPException: 成员不存在时返回 404。
    """
    with database.connect() as connection:
        member_exists = connection.execute('SELECT 1 FROM members WHERE id = ?', (member_id,)).fetchone()
    if member_exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='成员不存在')
    rows = _attendance_rows(member_id)
    return ApiResponse(data=_build_heatmap_payload(rows))