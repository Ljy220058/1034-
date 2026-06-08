from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..database import connect
from ..models import ApiResponse
from .common import CurrentUser, admin_or_leader, get_current_user

router = APIRouter(prefix='/api/v1/members/ranking', tags=['member-ranking'])


@dataclass(frozen=True)
class RankingRow:
    """成员跑量排行行记录。"""

    member_id: int
    member_name: str
    total_distance_km: float
    monthly_distance_km: float
    checkin_days: int
    average_pace: str

    def as_dict(self) -> dict[str, Any]:
        """转为可序列化字典。"""
        return {
            'member_id': self.member_id,
            'member_name': self.member_name,
            'total_distance_km': self.total_distance_km,
            'monthly_distance_km': self.monthly_distance_km,
            'checkin_days': self.checkin_days,
            'average_pace': self.average_pace,
        }


def _safe_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_month(month: str | None) -> tuple[date, date]:
    if month is None:
        today = datetime.now(timezone.utc).date()
        start = today.replace(day=1)
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1, day=1)
        else:
            next_month = start.replace(month=start.month + 1, day=1)
        return start, next_month
    try:
        parsed = datetime.strptime(month, '%Y-%m')
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='月份格式应为 YYYY-MM') from exc
    start = parsed.date().replace(day=1)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1, day=1)
    else:
        next_month = start.replace(month=start.month + 1, day=1)
    return start, next_month


def _average_pace(total_distance_km: float, total_seconds: float) -> str:
    if total_distance_km <= 0 or total_seconds <= 0:
        return '0:00/km'
    seconds_per_km = int(round(total_seconds / total_distance_km))
    minutes, seconds = divmod(seconds_per_km, 60)
    return f'{minutes}:{seconds:02d}/km'


def _load_ranking(month: str | None) -> list[RankingRow]:
    start_date, end_date = _parse_month(month)
    start_text = start_date.isoformat()
    end_text = end_date.isoformat()
    with connect() as connection:
        rows = connection.execute(
            (
                'SELECT m.id AS member_id, m.name AS member_name, '\
                'COALESCE(SUM(COALESCE(a.distance_km, 0)), 0) AS total_distance_km, '\
                'COALESCE(SUM(CASE WHEN DATE(COALESCE(at.signed_in_at, at.created_at)) >= ? '\
                'AND DATE(COALESCE(at.signed_in_at, at.created_at)) < ? '\
                'THEN COALESCE(a.distance_km, 0) ELSE 0 END), 0) AS monthly_distance_km, '\
                'COUNT(DISTINCT CASE WHEN DATE(COALESCE(at.signed_in_at, at.created_at)) >= ? '\
                'AND DATE(COALESCE(at.signed_in_at, at.created_at)) < ? '\
                'THEN DATE(COALESCE(at.signed_in_at, at.created_at)) END) AS checkin_days, '\
                'COALESCE(SUM(COALESCE(at.duration_minutes, 0)), 0) AS total_duration_minutes '\
                'FROM members m '\
                "LEFT JOIN attendances at ON at.member_id = m.id AND at.status = 'signed_in' "\
                'LEFT JOIN activities a ON a.id = at.activity_id '\
                'GROUP BY m.id, m.name '\
                'ORDER BY total_distance_km DESC, monthly_distance_km DESC, checkin_days DESC, m.id ASC'
            ),
            (start_text, end_text, start_text, end_text),
        ).fetchall()
    return [
        RankingRow(
            member_id=_safe_int(row['member_id']),
            member_name=str(row['member_name'] or ''),
            total_distance_km=_safe_float(row['total_distance_km']),
            monthly_distance_km=_safe_float(row['monthly_distance_km']),
            checkin_days=_safe_int(row['checkin_days']),
            average_pace=_average_pace(_safe_float(row['total_distance_km']), _safe_float(row['total_duration_minutes']) * 60),
        )
        for row in rows
    ]


def _load_member_statistics(member_id: int, month: str | None) -> dict[str, Any]:
    start_date, end_date = _parse_month(month)
    start_text = start_date.isoformat()
    end_text = end_date.isoformat()
    with connect() as connection:
        row = connection.execute(
            (
                'SELECT m.id AS member_id, m.name AS member_name, '\
                'COALESCE(SUM(CASE WHEN DATE(COALESCE(at.signed_in_at, at.created_at)) >= ? '\
                'AND DATE(COALESCE(at.signed_in_at, at.created_at)) < ? '\
                'THEN COALESCE(a.distance_km, 0) ELSE 0 END), 0) AS monthly_distance_km, '\
                'COUNT(DISTINCT CASE WHEN DATE(COALESCE(at.signed_in_at, at.created_at)) >= ? '\
                'AND DATE(COALESCE(at.signed_in_at, at.created_at)) < ? '\
                'THEN DATE(COALESCE(at.signed_in_at, at.created_at)) END) AS checkin_days, '\
                'COALESCE(SUM(COALESCE(at.duration_minutes, 0)), 0) AS total_duration_minutes '\
                'FROM members m '\
                "LEFT JOIN attendances at ON at.member_id = m.id AND at.status = 'signed_in' "\
                'LEFT JOIN activities a ON a.id = at.activity_id '\
                'WHERE m.id = ? '\
                'GROUP BY m.id, m.name'
            ),
            (start_text, end_text, start_text, end_text, member_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='成员不存在')
    monthly_distance_km = _safe_float(row['monthly_distance_km'])
    return {
        'member_id': _safe_int(row['member_id']),
        'member_name': str(row['member_name'] or ''),
        'monthly_distance_km': monthly_distance_km,
        'checkin_days': _safe_int(row['checkin_days']),
        'average_pace': _average_pace(monthly_distance_km, _safe_float(row['total_duration_minutes']) * 60),
    }


@router.get('', response_model=ApiResponse)
def read_member_ranking(
    current_user: CurrentUser = Depends(get_current_user),
    month: str | None = Query(default=None, description='月份，格式 YYYY-MM，默认当前月'),
) -> ApiResponse:
    """返回成员跑量排行列表。"""
    admin_or_leader(current_user)
    return ApiResponse(data=[row.as_dict() for row in _load_ranking(month)], message='成员跑量排行获取成功')


@router.get('/{member_id}', response_model=ApiResponse)
def read_member_statistics(
    member_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    month: str | None = Query(default=None, description='月份，格式 YYYY-MM，默认当前月'),
) -> ApiResponse:
    """返回指定成员的月度跑量、打卡天数和平均配速。"""
    admin_or_leader(current_user)
    return ApiResponse(data=_load_member_statistics(member_id, month), message='成员统计获取成功')
