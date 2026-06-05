from __future__ import annotations

import hashlib
import hmac

from fastapi import APIRouter, HTTPException, status

from ..db import initialize_database
from ..database import connect
from ..models import ApiResponse, UserLogin, UserRegister
from ..repository import create_member_with_password, get_member
from .common import member_to_public, sanitize_member_payload, token_for_member

router = APIRouter(prefix='/api/v1/auth', tags=['auth'])


@router.post('/register', response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister) -> ApiResponse:
    password_hash = hashlib.sha256(payload.password.encode('utf-8')).hexdigest()
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
    initialize_database()
    with connect() as connection:
        row = connection.execute('SELECT * FROM members WHERE phone = ?', (payload.phone,)).fetchone()
    if row is None or not row['password_hash']:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
    expected = row['password_hash']
    actual = hashlib.sha256(payload.password.encode('utf-8')).hexdigest()
    if not hmac.compare_digest(expected, actual):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
    member = get_member(row['id'])
    if member is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid phone or password')
    token = token_for_member(member)
    return ApiResponse(data={'token_type': 'Bearer', 'access_token': token, 'member': member_to_public(member)})
