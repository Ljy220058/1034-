from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix='/api/v1/activity_digest', tags=['activity_digest'])


@router.get('')
def get_activity_digest() -> dict[str, Any]:
    """返回活动摘要占位响应。

    Returns:
        ApiResponse 风格的响应体。
    """
    return {'data': {'overview': {}}, 'message': '成功'}
