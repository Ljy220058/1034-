from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..models import ApiResponse
from .common import CurrentUser, get_current_user

router = APIRouter(prefix='/api/v1', tags=['idle-task-recommender'])


@router.get('/idle-task/recommendations', response_model=ApiResponse)
def recommend_idle_tasks(
    current_user: CurrentUser = Depends(get_current_user),
    keyword: str = Query(default='', min_length=0, max_length=200),
) -> ApiResponse:
    """返回空闲任务推荐。

    Args:
        current_user: 当前登录用户。
        keyword: 任务关键词。

    Returns:
        包含推荐结果的标准响应。

    Raises:
        HTTPException: 当关键词非法时返回 422。
    """
    if not keyword.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='关键词不能为空')

    return ApiResponse(
        data={
            'keyword': keyword.strip(),
            'recommendations': [
                {'title': '补充训练计划', 'priority': 1},
                {'title': '整理活动报名', 'priority': 2},
                {'title': '清理过期任务', 'priority': 3},
            ],
            'current_user_id': current_user.id,
        },
        message='成功',
    )
