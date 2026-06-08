from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..models import ApiResponse, MemberCreate, MemberUpdate, UserLogin, UserRegister
from ..repository import create_member, delete_member, get_member, list_members, update_member
from .common import (
    CurrentUser,
    ROLE_ADMIN,
    ROLE_LEADER,
    ROLE_MEMBER,
    admin_or_leader,
    get_current_user,
    member_read_guard,
    member_to_public,
    member_write_guard,
)

router = APIRouter(prefix='/api/v1/members', tags=['members'])


@router.get('', response_model=ApiResponse)
def read_members(current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    members = list_members()
    return ApiResponse(data=[member_to_public(member) for member in members])


@router.post('', response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_member_endpoint(payload: MemberCreate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    if current_user.role != ROLE_ADMIN and payload.role != ROLE_MEMBER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='forbidden')
    if payload.role not in {ROLE_MEMBER, ROLE_ADMIN, ROLE_LEADER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='invalid role')
    import hashlib, secrets
    member_data = payload.model_dump(exclude={'role'})
    member_data['password_hash'] = ''
    member_id = create_member(**member_data)
    member = get_member(member_id)
    return ApiResponse(data=member_to_public(member))


@router.get('/me', response_model=ApiResponse)
def read_me(current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    return ApiResponse(data=member_to_public(current_user.member))


@router.get('/{member_id}', response_model=ApiResponse)
def read_member(member_id: int, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    member_read_guard(member_id, current_user)
    member = get_member(member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='member not found')
    return ApiResponse(data=member_to_public(member))


@router.patch('/{member_id}', response_model=ApiResponse)
def patch_member(member_id: int, payload: MemberUpdate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    member_write_guard(member_id, current_user)
    if payload.role is not None and payload.role not in {ROLE_MEMBER, ROLE_ADMIN, ROLE_LEADER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='invalid role')
    if current_user.role != ROLE_ADMIN and payload.role is not None and payload.role != ROLE_MEMBER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='forbidden')
    if payload.role is not None and current_user.role != ROLE_ADMIN:
        payload.role = ROLE_MEMBER
    member = update_member(member_id, payload)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='member not found')
    return ApiResponse(data=member_to_public(member))


@router.delete('/{member_id}', response_model=ApiResponse)
def remove_member(member_id: int, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    target = get_member(member_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='member not found')
    if target.role != ROLE_MEMBER:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='member not found')
    deleted = delete_member(member_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='member not found')
    return ApiResponse(data={'deleted': True})


@router.post('/register', response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def register_member(payload: UserRegister) -> ApiResponse:
    """注册成员账号。"""
    member_data = payload.model_dump(exclude={'password'})
    member_id = create_member(**member_data)
    member = get_member(member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='服务器内部错误')
    return ApiResponse(data=member_to_public(member))


@router.post('/login', response_model=ApiResponse)
def login_member(payload: UserLogin) -> ApiResponse:
    """登录成员账号。"""
    member = None
    for item in list_members():
        if getattr(item, 'phone', None) == payload.phone:
            member = item
            break
    if member is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='账号或密码错误')
    return ApiResponse(data={'access_token': f'{member.id}:{member.role}:2099-01-01T00:00:00+00:00'})
