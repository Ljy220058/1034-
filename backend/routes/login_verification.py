from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..models import ApiResponse

router = APIRouter(prefix='/api/v1/login-verification', tags=['login-verification'])


@router.get('/status')
def login_verification_status() -> dict[str, Any]:
    """返回登录校验路由状态。

    Returns:
        ApiResponse 结构的路由状态数据。
    """
    return ApiResponse(
        data={'enabled': True, 'name': 'login_verification'},
        message='登录校验路由可用',
    ).model_dump()
