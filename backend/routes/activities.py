from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix='/api/v1/activities', tags=['activities'])


@router.get('')
def list_activities() -> dict[str, Any]:
    """返回活动列表占位响应。"""
    return {'data': [], 'message': '成功'}


@router.post('', status_code=201)
def create_activity() -> dict[str, Any]:
    """创建活动的占位实现。"""
    return {'data': {'id': 1, 'title': '晨跑', 'start_time': datetime.now(timezone.utc).isoformat()}, 'message': '成功'}
