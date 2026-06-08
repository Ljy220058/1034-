from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from ..models import AnnouncementCreate, AnnouncementUpdate, ApiResponse
from ..repository import create_announcement, delete_announcement, get_announcement, list_announcements, update_announcement
from .common import CurrentUser, admin_or_leader, announcement_payload, get_current_user, get_optional_current_user

router = APIRouter(prefix='/api/v1/announcements', tags=['announcements'])


@router.get('', response_model=ApiResponse)
def read_announcements(current_user: CurrentUser = Depends(get_current_user), status: str | None = Query(default=None)) -> ApiResponse:
    announcements = list_announcements(status=status)
    return ApiResponse(data=[announcement.model_dump(mode='json') for announcement in announcements])


@router.post('', response_model=ApiResponse, status_code=201)
def create_announcement_endpoint(payload: AnnouncementCreate = Body(...), current_user: CurrentUser | None = Depends(get_optional_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    data = announcement_payload(payload)
    record = create_announcement(AnnouncementCreate(**data))
    return ApiResponse(data=record.model_dump(mode='json'))


@router.get('/{announcement_id}', response_model=ApiResponse)
def read_announcement(announcement_id: int, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    announcement = get_announcement(announcement_id)
    if announcement is None:
        raise HTTPException(status_code=404, detail='announcement not found')
    return ApiResponse(data=announcement.model_dump(mode='json'))


@router.patch('/{announcement_id}', response_model=ApiResponse)
def patch_announcement(announcement_id: int, payload: AnnouncementUpdate = Body(...), current_user: CurrentUser | None = Depends(get_optional_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    data = payload.model_dump(exclude_unset=True)
    announcement = update_announcement(announcement_id, AnnouncementUpdate(**data))
    if announcement is None:
        raise HTTPException(status_code=404, detail='announcement not found')
    return ApiResponse(data=announcement.model_dump(mode='json'))


@router.delete('/{announcement_id}', response_model=ApiResponse)
def remove_announcement(announcement_id: int, current_user: CurrentUser | None = Depends(get_optional_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    deleted = delete_announcement(announcement_id)
    if not deleted:
        raise HTTPException(status_code=404, detail='announcement not found')
    return ApiResponse(data={'deleted': True})
