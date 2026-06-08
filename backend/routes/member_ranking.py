from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from ..database import connect
from ..models import ApiResponse
from .common import CurrentUser, admin_or_leader, get_current_user

router = APIRouter(prefix='/api/v1/members/ranking', tags=['member-ranking'])


def _fetch_member_ranking() -> list[dict[str, Any]]:
    """查询成员总跑量排行。

    Returns:
        按总跑量降序排列的成员排行列表。
    """
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT
                m.id AS member_id,
                m.name AS member_name,
                m.phone AS phone,
                COUNT(DISTINCT a.id) AS signed_in_activities,
                COALESCE(SUM(COALESCE(a.distance_km, 0)), 0) AS total_distance_km,
                COALESCE(SUM(CASE
                    WHEN strftime('%Y-%m', COALESCE(at.signed_in_at, at.created_at)) = strftime('%Y-%m', 'now')
                    THEN COALESCE(a.distance_km, 0)
                    ELSE 0
                END), 0) AS monthly_distance_km,
                COUNT(DISTINCT DATE(COALESCE(at.signed_in_at, at.created_at))) AS checkin_days,
                CASE
                    WHEN COUNT(DISTINCT a.id) = 0 THEN 0.0
                    ELSE ROUND(SUM(COALESCE(a.distance_km, 0)) / COUNT(DISTINCT a.id), 2)
                END AS average_pace_score
            FROM members m
            LEFT JOIN attendances at ON at.member_id = m.id AND at.status = 'signed_in'
            LEFT JOIN activities a ON a.id = at.activity_id
            GROUP BY m.id, m.name, m.phone
            ORDER BY total_distance_km DESC, signed_in_activities DESC, m.id ASC
            """
        ).fetchall()
    return [
        {
            'member_id': row[0],
            'member_name': row[1],
            'phone': row[2],
            'signed_in_activities': row[3],
            'total_distance_km': row[4] or 0,
            'monthly_distance_km': row[5] or 0,
            'checkin_days': row[6] or 0,
            'average_pace_score': row[7] or 0,
        }
        for row in rows
    ]


def _fetch_member_statistics(member_id: int) -> dict[str, Any]:
    """查询指定成员的跑步统计数据。"""
    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                m.id AS member_id,
                m.name AS member_name,
                COALESCE(SUM(CASE
                    WHEN strftime('%Y-%m', COALESCE(at.signed_in_at, at.created_at)) = strftime('%Y-%m', 'now')
                    THEN COALESCE(a.distance_km, 0)
                    ELSE 0
                END), 0) AS monthly_distance_km,
                COUNT(DISTINCT DATE(COALESCE(at.signed_in_at, at.created_at))) AS checkin_days,
                CASE
                    WHEN COUNT(DISTINCT a.id) = 0 THEN 0.0
                    ELSE ROUND(SUM(COALESCE(a.distance_km, 0)) / COUNT(DISTINCT a.id), 2)
                END AS average_pace_score
            FROM members m
            LEFT JOIN attendances at ON at.member_id = m.id AND at.status = 'signed_in'
            LEFT JOIN activities a ON a.id = at.activity_id
            WHERE m.id = ?
            GROUP BY m.id, m.name
            """,
            (member_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='成员不存在')
    return {
        'member_id': row[0],
        'member_name': row[1],
        'monthly_distance_km': row[2] or 0,
        'checkin_days': row[3] or 0,
        'average_pace_score': row[4] or 0,
    }


@router.get('', response_model=ApiResponse)
def read_member_ranking(current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    """返回成员跑量排行列表。"""
    admin_or_leader(current_user)
    return ApiResponse(data=_fetch_member_ranking(), message='成员跑量排行获取成功')


@router.get('/{member_id}', response_model=ApiResponse)
def read_member_statistics(member_id: int, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    """返回指定成员的月度跑量、打卡天数和平均配速。"""
    admin_or_leader(current_user)
    return ApiResponse(data=_fetch_member_statistics(member_id), message='成员统计获取成功')
