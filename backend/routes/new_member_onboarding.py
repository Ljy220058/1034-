from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..models import ApiResponse

router = APIRouter(prefix='/api/v1/onboarding', tags=['onboarding'])

DB_PATH = Path(__file__).resolve().parents[2] / 'data' / 'running_club.db'


class PairRequest(BaseModel):
    """老带新配对请求。"""

    member_id: int = Field(gt=0)


class PairingOut(BaseModel):
    """老带新配对结果。"""

    new_member_id: int
    mentor_member_id: int
    mentor_name: str
    mentor_pace_group: str | None = None


def _connect_db() -> sqlite3.Connection:
    """建立数据库连接。

    Returns:
        SQLite 连接对象。
    """
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _fetch_one(connection: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> sqlite3.Row | None:
    """执行只读查询并返回单行结果。

    Args:
        connection: 数据库连接。
        query: 参数化 SQL。
        params: SQL 参数。

    Returns:
        查询到的单行记录或 None。
    """
    return connection.execute(query, params).fetchone()


def _fetch_member(connection: sqlite3.Connection, member_id: int) -> sqlite3.Row | None:
    return _fetch_one(
        connection,
        'SELECT id, name, pace_group, training_goal, phone, role, running_years, usual_distance_km FROM members WHERE id = ?',
        (member_id,),
    )


def _build_status_payload(connection: sqlite3.Connection, member_id: int) -> dict[str, Any]:
    member = _fetch_member(connection, member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='成员不存在')

    first_checkin = _fetch_one(
        connection,
        'SELECT MIN(signed_in_at) AS first_checked_in_at FROM attendances WHERE member_id = ? AND status = ? ',
        (member_id, 'signed_in'),
    )
    first_activity = _fetch_one(
        connection,
        '''
        SELECT a.id, a.title, a.start_time
        FROM attendances atn
        JOIN activities a ON a.id = atn.activity_id
        WHERE atn.member_id = ? AND atn.status = ?
        ORDER BY a.start_time ASC, a.id ASC
        LIMIT 1
        ''',
        (member_id, 'signed_in'),
    )
    wechat_group = _fetch_one(
        connection,
        'SELECT group_name, joined_at FROM member_groups WHERE member_id = ? ORDER BY joined_at ASC, id ASC LIMIT 1',
        (member_id,),
    )

    return {
        'member': {
            'id': member['id'],
            'name': member['name'],
            'pace_group': member['pace_group'],
            'training_goal': member['training_goal'],
            'phone': member['phone'],
            'role': member['role'],
            'running_years': member['running_years'],
            'usual_distance_km': member['usual_distance_km'],
        },
        'completion': {
            'profile_completed': bool(member['name']),
            'first_checkin_completed': first_checkin is not None and first_checkin['first_checked_in_at'] is not None,
            'first_activity_completed': first_activity is not None,
            'wechat_group_joined': wechat_group is not None,
        },
        'first_checkin': {
            'completed': first_checkin is not None and first_checkin['first_checked_in_at'] is not None,
            'first_checked_in_at': first_checkin['first_checked_in_at'] if first_checkin is not None else None,
        },
        'first_activity': None
        if first_activity is None
        else {
            'completed': True,
            'activity_id': first_activity['id'],
            'activity_title': first_activity['title'],
            'activity_start_time': first_activity['start_time'],
        },
        'wechat_group': {
            'completed': wechat_group is not None,
            'group_name': wechat_group['group_name'] if wechat_group is not None else None,
            'joined_at': wechat_group['joined_at'] if wechat_group is not None else None,
        },
    }


@router.get('/status/{member_id}', response_model=ApiResponse)
def get_onboarding_status(member_id: int) -> ApiResponse:
    """获取新人成长引导完成情况。

    Args:
        member_id: 成员 ID。

    Returns:
        ApiResponse 包装的完成状态。
    """
    try:
        with _connect_db() as connection:
            data = _build_status_payload(connection, member_id)
    except sqlite3.Error:
        raise HTTPException(status_code=500, detail='数据库查询失败') from None
    return ApiResponse(data=data, message='成功')


@router.post('/pair', response_model=ApiResponse)
def create_pairing(payload: PairRequest) -> ApiResponse:
    """为新成员匹配老带新搭档。

    Args:
        payload: 新成员 ID。

    Returns:
        ApiResponse 包装的配对结果。
    """
    try:
        with _connect_db() as connection:
            member = _fetch_member(connection, payload.member_id)
            if member is None:
                raise HTTPException(status_code=404, detail='新成员不存在')
            mentor = _fetch_one(
                connection,
                '''
                SELECT id, name, pace_group
                FROM members
                WHERE id != ?
                ORDER BY COALESCE(running_years, 0) DESC, id ASC
                LIMIT 1
                ''',
                (payload.member_id,),
            )
            if mentor is None:
                raise HTTPException(status_code=404, detail='暂无可用老成员')
    except sqlite3.Error:
        raise HTTPException(status_code=500, detail='数据库查询失败') from None

    return ApiResponse(
        data=PairingOut(
            new_member_id=payload.member_id,
            mentor_member_id=mentor['id'],
            mentor_name=mentor['name'],
            mentor_pace_group=mentor['pace_group'],
        ).model_dump(),
        message='成功',
    )


@router.get('/welcome-checklist/{member_id}', response_model=ApiResponse)
def get_welcome_checklist(member_id: int) -> ApiResponse:
    """获取新成员欢迎清单。

    Args:
        member_id: 成员 ID。

    Returns:
        ApiResponse 包装的清单信息。
    """
    try:
        with _connect_db() as connection:
            status_payload = _build_status_payload(connection, member_id)
    except sqlite3.Error:
        raise HTTPException(status_code=500, detail='数据库查询失败') from None
    checklist = [
        {'key': 'profile_completed', 'label': '完善个人信息', 'done': status_payload['completion']['profile_completed']},
        {'key': 'first_checkin_completed', 'label': '完成首次签到', 'done': status_payload['completion']['first_checkin_completed']},
        {'key': 'first_activity_completed', 'label': '完成首次参与活动', 'done': status_payload['completion']['first_activity_completed']},
        {'key': 'wechat_group_joined', 'label': '加入微信群', 'done': status_payload['completion']['wechat_group_joined']},
    ]
    return ApiResponse(
        data={'member_id': member_id, 'items': checklist, 'all_completed': all(item['done'] for item in checklist)},
        message='成功',
    )
