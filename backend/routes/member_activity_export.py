from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from ..database import connect, init_db
from ..models import ApiResponse
from ..repository import get_member
from .common import CurrentUser, get_current_user

router = APIRouter(prefix='/api/v1/members', tags=['members'])


@dataclass(frozen=True)
class ActivityExportRow:
    """成员活动轨迹导出条目。"""

    activity_id: int
    activity_title: str
    activity_start_time: str
    status: str
    registration_status: str | None
    attendance_status: str | None
    signed_in_at: str | None
    distance_km: float
    note: str | None

    def model_dump(self) -> dict[str, Any]:
        """序列化导出条目。"""
        return {
            'activity_id': self.activity_id,
            'activity_title': self.activity_title,
            'activity_start_time': self.activity_start_time,
            'status': self.status,
            'registration_status': self.registration_status,
            'attendance_status': self.attendance_status,
            'signed_in_at': self.signed_in_at,
            'distance_km': self.distance_km,
            'note': self.note,
        }


class MemberActivityExportQuery(BaseModel):
    """成员活动轨迹导出查询。"""

    member_id: int = Field(gt=0)
    start_date: str | None = None
    end_date: str | None = None

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        """校验日期格式。"""
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            date.fromisoformat(cleaned)
        except ValueError as exc:
            raise ValueError('日期格式必须为 YYYY-MM-DD') from exc
        return cleaned


def _parse_iso_date(value: str | None) -> date | None:
    """解析 ISO 日期。"""
    if value is None:
        return None
    return date.fromisoformat(value)


def _to_utc_iso(value: str | None) -> str | None:
    """规范化 ISO 时间字符串。"""
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def _within_range(activity_date: date, start_date: date | None, end_date: date | None) -> bool:
    """判断活动日期是否在查询范围内。"""
    if start_date is not None and activity_date < start_date:
        return False
    if end_date is not None and activity_date > end_date:
        return False
    return True


def _fetch_member_activity_rows(member_id: int, start_date: str | None, end_date: str | None) -> list[ActivityExportRow]:
    """复用 members / activities / registrations / attendances 查询成员活动轨迹。"""
    init_db()
    start = _parse_iso_date(start_date)
    end = _parse_iso_date(end_date)
    with connect() as connection:
        member_row = connection.execute('SELECT * FROM members WHERE id = ?', (member_id,)).fetchone()
        if member_row is None:
            return []
        rows = connection.execute(
            '''
            SELECT
                a.id AS activity_id,
                a.title AS activity_title,
                a.start_time AS activity_start_time,
                a.distance_km AS distance_km,
                r.status AS registration_status,
                t.status AS attendance_status,
                t.signed_in_at AS signed_in_at
            FROM activities a
            LEFT JOIN registrations r ON r.activity_id = a.id AND r.member_id = ?
            LEFT JOIN attendances t ON t.activity_id = a.id AND t.member_id = ?
            WHERE r.member_id = ? OR t.member_id = ?
            ORDER BY a.start_time DESC, a.id DESC
            ''',
            (member_id, member_id, member_id, member_id),
        ).fetchall()

    exported: list[ActivityExportRow] = []
    for row in rows:
        start_time = _to_utc_iso(row['activity_start_time'])
        if start_time is None:
            continue
        activity_date = datetime.fromisoformat(start_time).date()
        if not _within_range(activity_date, start, end):
            continue
        attendance_status = row['attendance_status']
        if attendance_status is None and row['signed_in_at'] is not None:
            attendance_status = 'signed_in'
        registration_status = row['registration_status']
        if registration_status is None and attendance_status is not None:
            registration_status = 'registered'
        exported.append(
            ActivityExportRow(
                activity_id=int(row['activity_id']),
                activity_title=str(row['activity_title']),
                activity_start_time=start_time,
                status='已签到' if attendance_status == 'signed_in' else ('已报名' if registration_status == 'registered' else '未参与'),
                registration_status=registration_status,
                attendance_status=attendance_status,
                signed_in_at=_to_utc_iso(row['signed_in_at']),
                distance_km=float(row['distance_km'] or 0),
                note='签到记录已纳入统计' if attendance_status == 'signed_in' else '仅报名记录',
            )
        )
    return exported


def _build_summary(member: dict[str, Any], rows: list[ActivityExportRow]) -> dict[str, Any]:
    """构造导出摘要。"""
    signed_in_count = sum(1 for row in rows if row.attendance_status == 'signed_in')
    total_distance = sum(row.distance_km for row in rows if row.attendance_status == 'signed_in')
    return {
        'member': member,
        'activities': [row.model_dump() for row in rows],
        'summary': {
            'signed_in_count': signed_in_count,
            'total_distance_km': round(total_distance, 2),
            'total_activity_count': len(rows),
        },
    }


def _build_csv(rows: list[ActivityExportRow]) -> str:
    """导出 CSV 字符串。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['activity_id', 'activity_title', 'activity_start_time', 'status', 'registration_status', 'attendance_status', 'signed_in_at', 'distance_km', 'note'])
    for row in rows:
        writer.writerow([
            row.activity_id,
            row.activity_title,
            row.activity_start_time,
            row.status,
            row.registration_status or '',
            row.attendance_status or '',
            row.signed_in_at or '',
            row.distance_km,
            row.note or '',
        ])
    return buffer.getvalue()


@router.get('/activity-trace/export', response_model=ApiResponse)
def export_member_activity_trace(
    member_id: int = Query(..., gt=0, description='成员ID'),
    start_date: str | None = Query(default=None, description='开始日期，格式 YYYY-MM-DD'),
    end_date: str | None = Query(default=None, description='结束日期，格式 YYYY-MM-DD'),
    format: str = Query(default='json', description='导出格式：json 或 csv'),
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    """导出成员活动轨迹。

    Args:
        member_id: 成员 ID。
        start_date: 可选开始日期。
        end_date: 可选结束日期。
        format: 导出格式，支持 json 和 csv。
        current_user: 当前登录用户。

    Returns:
        结构化导出结果。

    Raises:
        HTTPException: 成员不存在、日期非法或格式非法时抛出。
    """
    _ = current_user
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='开始日期不能晚于结束日期')
    member = get_member(member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='成员不存在')
    rows = _fetch_member_activity_rows(member_id, start_date, end_date)
    payload = _build_summary(member.model_dump(), rows)
    if format.lower() == 'csv':
        payload = {**payload, 'csv': _build_csv(rows)}
        return ApiResponse(data=payload, message='已导出成员活动轨迹 CSV')
    if format.lower() != 'json':
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='导出格式仅支持 json 或 csv')
    return ApiResponse(data=payload, message='已导出成员活动轨迹')
