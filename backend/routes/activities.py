from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..models import ActivityCreate, ActivityUpdate, ApiResponse, RegistrationCreate
from ..activity_registration_risk import create_activity
from ..repository import cancel_registration, create_registration, delete_activity, get_activity, get_registration_status, list_activities, list_registration_statuses, registration_risk_smoke_panel, update_activity
from .common import CurrentUser, ROLE_ADMIN, ROLE_LEADER, admin_or_leader, get_current_user, get_optional_current_user, registration_member_guard

router = APIRouter(prefix='/api/v1/activities', tags=['activities'])


def _create_activity(payload: ActivityCreate):
    """Create an activity using the shared activity module.

    Args:
        payload: Activity creation request body.

    Returns:
        Created activity model.
    """
    return create_activity(payload)


def _filter_ended_activities(activities: list[object], only_unended: bool) -> list[object]:
    """过滤活动列表。

    Args:
        activities: 活动记录列表。
        only_unended: 是否仅返回未结束活动。

    Returns:
        过滤后的活动记录列表。
    """
    if not only_unended:
        return activities
    return [activity for activity in activities if getattr(activity, 'ended', False) is False]


def _activity_payload(activity: object, registration_status: str) -> dict[str, object]:
    """构造带报名状态的活动响应数据。

    Args:
        activity: 活动记录。
        registration_status: 当前成员对活动的报名状态。

    Returns:
        活动响应字典。
    """
    data = activity.model_dump(mode='json')
    data['registration_status'] = registration_status
    data['is_registered'] = registration_status == 'registered'
    return data


@router.get('', response_model=ApiResponse)
def read_activities(
    current_user: CurrentUser | None = Depends(get_optional_current_user),
    only_unended: bool = Query(default=False, description='仅返回未结束活动'),
) -> ApiResponse:
    """读取活动列表。

    Args:
        current_user: 当前登录用户；未登录时为 None。
        only_unended: 是否仅返回未结束活动。

    Returns:
        包含活动列表的标准响应。
    """
    activities = _filter_ended_activities(list_activities(), only_unended)
    member_id = current_user.id if current_user is not None else None
    statuses = list_registration_statuses([int(activity.id) for activity in activities], member_id)
    return ApiResponse(data=[_activity_payload(activity, statuses[int(activity.id)]) for activity in activities])


@router.post('', response_model=ApiResponse, status_code=201)
def create_activity_endpoint(payload: ActivityCreate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    """创建活动。"""
    admin_or_leader(current_user)
    if current_user.role not in {ROLE_ADMIN, ROLE_LEADER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='forbidden')
    activity = _create_activity(payload)
    return ApiResponse(data=activity.model_dump(mode='json'))


@router.get('/{activity_id}', response_model=ApiResponse)
def read_activity(activity_id: int, current_user: CurrentUser | None = Depends(get_optional_current_user)) -> ApiResponse:
    """读取活动详情。

    Args:
        activity_id: 活动编号。
        current_user: 当前登录用户；未登录时为 None。

    Returns:
        包含活动详情的标准响应。
    """
    activity = get_activity(activity_id)
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='activity not found')
    member_id = current_user.id if current_user is not None else None
    return ApiResponse(data=_activity_payload(activity, get_registration_status(activity_id, member_id)))


@router.patch('/{activity_id}', response_model=ApiResponse)
def patch_activity(activity_id: int, payload: ActivityUpdate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    """更新活动。"""
    admin_or_leader(current_user)
    activity = update_activity(activity_id, payload)
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='activity not found')
    return ApiResponse(data=activity.model_dump(mode='json'))


@router.delete('/{activity_id}', response_model=ApiResponse)
def remove_activity(activity_id: int, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    """删除活动。"""
    admin_or_leader(current_user)
    deleted = delete_activity(activity_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='activity not found')
    return ApiResponse(data={'deleted': True})


@router.get('/{activity_id}/registration-risk-smoke-panel', response_model=ApiResponse)
def read_registration_risk_smoke_panel(activity_id: int, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    """读取报名风险冒烟面板。"""
    admin_or_leader(current_user)
    activity = get_activity(activity_id)
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='activity not found')
    return ApiResponse(data=registration_risk_smoke_panel(activity))


@router.get('/{activity_id}/digest', response_model=ApiResponse)
def read_activity_digest(activity_id: int, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    """读取活动摘要。"""
    _ = current_user
    activity = get_activity(activity_id)
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='activity not found')
    return ApiResponse(
        data={
            'activity': activity.model_dump(mode='json'),
            'overview': {
                'registered_count': 0,
                'signed_in_count': 0,
                'absent_count': 0,
            },
            'absent_members': [],
            'follow_up_suggestions': ['补充报名统计', '查看签到情况'],
            'feedback_summary': '暂无反馈',
        }
    )


@router.post('/{activity_id}/registrations', response_model=ApiResponse, status_code=201)
def create_registration_endpoint(activity_id: int, payload: RegistrationCreate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    """创建报名。"""
    registration_member_guard(payload.member_id, current_user)
    registration, outcome = create_registration(activity_id, payload.member_id)
    if outcome == 'full':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='活动名额已满')
    if outcome == 'not_found' or registration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='activity not found')
    if outcome == 'conflict':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='成员已报名该活动')
    return ApiResponse(data=registration.model_dump(mode='json'))


@router.delete('/{activity_id}/registrations/{member_id}', response_model=ApiResponse)
def cancel_registration_endpoint(activity_id: int, member_id: int, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    """取消报名。"""
    registration_member_guard(member_id, current_user)
    cancelled = cancel_registration(activity_id, member_id)
    if cancelled is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='registration not found')
    return ApiResponse(data=cancelled.model_dump(mode='json'))
