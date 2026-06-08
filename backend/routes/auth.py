from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status

from ..db import initialize_database
from ..database import connect
from ..models import ApiResponse, UserLogin, UserRegister
from ..passwords import hash_password, is_strong_password_hash, verify_password
from ..repository import create_member_with_password, get_member
from .common import member_to_public, sanitize_member_payload, token_for_member

router = APIRouter(prefix='/api/v1/auth', tags=['auth'])


@router.post('/register', response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister) -> ApiResponse:
    """注册新成员并写入强密码哈希。

    Args:
        payload: 注册请求体。

    Returns:
        包含访问令牌和公开成员信息的标准响应。

    Raises:
        HTTPException: 手机号重复或角色越权时抛出结构化错误。
    """
    password_hash = hash_password(payload.password)
    try:
        member, outcome = create_member_with_password(sanitize_member_payload(payload), password_hash)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_403_FORBIDDEN and isinstance(exc.detail, dict):
            message = exc.detail.get('error', {}).get('message') if isinstance(exc.detail.get('error'), dict) else None
            if message:
                raise HTTPException(status_code=exc.status_code, detail=message) from exc
        raise
    if outcome == 'conflict' or member is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='phone already registered')
    token = token_for_member(member)
    return ApiResponse(data={'token_type': 'Bearer', 'access_token': token, 'member': member_to_public(member)})


@router.post('/login', response_model=ApiResponse)
def login(payload: UserLogin) -> ApiResponse:
    """登录成员并兼容升级旧版 SHA-256 密码哈希。

    Args:
        payload: 登录请求体。

    Returns:
        包含访问令牌和公开成员信息的标准响应。

    Raises:
        HTTPException: 手机号或密码错误时返回 401。
    """
    initialize_database()
    with connect() as connection:
        row = connection.execute('SELECT * FROM members WHERE phone = ?', (payload.phone,)).fetchone()
    if row is None:
        _ = verify_password(payload.password, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
    password_hash = row['password_hash']
    if not verify_password(payload.password, password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
    if not is_strong_password_hash(password_hash):
        upgraded_hash = hash_password(payload.password)
        with connect() as connection:
            connection.execute(
                'UPDATE members SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (upgraded_hash, row['id']),
            )
    member = get_member(row['id'])
    if member is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
    token = token_for_member(member)
    return ApiResponse(data={'token_type': 'Bearer', 'access_token': token, 'member': member_to_public(member)})
