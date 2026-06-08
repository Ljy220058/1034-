from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix='/api/v1/training_plan_completion', tags=['training_plan_completion'])


@router.get('')
def get_training_plan_completion() -> dict[str, Any]:
    """返回训练计划完成占位响应。

    Returns:
        ApiResponse 风格的响应体。
    """
    return {'data': {'completed': 0}, 'message': '成功'}
