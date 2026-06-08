from __future__ import annotations

from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, status

from ..models import ApiResponse, AttendanceCreate
from ..repository import create_attendance, delete_attendance, get_activity, get_attendance, get_member, list_activity_attendance
from .common import CurrentUser, admin_or_leader, get_current_user

router = APIRouter(prefix='/api/v1/activities/{activity_id}/checkins', tags=['checkins'])


def _coerce_attendance_payload(activity_id: int, payload: AttendanceCreate) -> AttendanceCreate:
    if payload.activity_id != activity_id:
        payload.activity_id = activity_id
    if payload.checked_in_at is not None and payload.checked_in_at.tzinfo is None:
        payload.checked_in_at = payload.checked_in_at.replace(tzinfo=timezone.utc)
    return payload


@router.get('', response_model=ApiResponse)
def read_activity_checkins(activity_id: int, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    attendance = list_activity_attendance(activity_id)
    return ApiResponse(data=[record.model_dump(mode='json') for record in attendance])


@router.post('', response_model=ApiResponse, status_code=201)
def create_checkin(activity_id: int, payload: AttendanceCreate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    if current_user.role not in {'admin', 'leader'} and current_user.id != payload.member_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='forbidden')
    payload = _coerce_attendance_payload(activity_id, payload)
    activity = get_activity(activity_id)
    member = get_member(payload.member_id)
    if activity is None or member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='activity or member not found')
    attendance, outcome = create_attendance(activity_id, payload.member_id, gps_checked=payload.gps_checked, checked_in_at=payload.checked_in_at)
    if outcome == 'not_found' or attendance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='activity or member not found')
    if outcome == 'not_registered':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='member is not registered for this activity')
    return ApiResponse(data=attendance.model_dump(mode='json'))


@router.get('/{attendance_id}', response_model=ApiResponse)
def read_checkin(activity_id: int, attendance_id: int, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    attendance = get_attendance(attendance_id)
    if attendance is None or attendance.activity_id != activity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='attendance not found')
    return ApiResponse(data=attendance.model_dump(mode='json'))


@router.delete('/{attendance_id}', response_model=ApiResponse)
def delete_checkin(activity_id: int, attendance_id: int, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    attendance = get_attendance(attendance_id)
    if attendance is None or attendance.activity_id != activity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='attendance not found')
    deleted = delete_attendance(attendance_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='attendance not found')
    return ApiResponse(data={'deleted': True})
