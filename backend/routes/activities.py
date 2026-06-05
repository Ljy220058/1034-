from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..models import ActivityCreate, ActivityUpdate, ApiResponse, RegistrationCreate
from ..repository import create_activity, create_registration, delete_activity, get_activity, list_activities, update_activity, cancel_registration, get_member
from .common import CurrentUser, ROLE_ADMIN, ROLE_LEADER, admin_or_leader, get_current_user, registration_member_guard

router = APIRouter(prefix='/api/v1/activities', tags=['activities'])


@router.get('', response_model=ApiResponse)
def read_activities(current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    activities = list_activities()
    return ApiResponse(data=[activity.model_dump(mode='json') for activity in activities])


@router.post('', response_model=ApiResponse, status_code=201)
def create_activity_endpoint(payload: ActivityCreate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    if current_user.role not in {ROLE_ADMIN, ROLE_LEADER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='forbidden')
    activity = create_activity(payload)
    return ApiResponse(data=activity.model_dump(mode='json'))


@router.get('/{activity_id}', response_model=ApiResponse)
def read_activity(activity_id: int, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    activity = get_activity(activity_id)
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='activity not found')
    return ApiResponse(data=activity.model_dump(mode='json'))


@router.patch('/{activity_id}', response_model=ApiResponse)
def patch_activity(activity_id: int, payload: ActivityUpdate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    activity = update_activity(activity_id, payload)
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='activity not found')
    return ApiResponse(data=activity.model_dump(mode='json'))


@router.delete('/{activity_id}', response_model=ApiResponse)
def remove_activity(activity_id: int, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    deleted = delete_activity(activity_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='activity not found')
    return ApiResponse(data={'deleted': True})


@router.post('/{activity_id}/registrations', response_model=ApiResponse, status_code=201)
def create_registration_endpoint(activity_id: int, payload: RegistrationCreate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    registration_member_guard(payload.member_id, current_user)
    registration, outcome = create_registration(activity_id, payload.member_id)
    if outcome == 'not_found' or registration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='activity not found')
    if outcome == 'conflict':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='member already registered for this activity')
    return ApiResponse(data=registration.model_dump(mode='json'))


@router.delete('/{activity_id}/registrations/{member_id}', response_model=ApiResponse)
def cancel_registration_endpoint(activity_id: int, member_id: int, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    registration_member_guard(member_id, current_user)
    cancelled = cancel_registration(activity_id, member_id)
    if cancelled is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='registration not found')
    return ApiResponse(data=cancelled.model_dump(mode='json'))
