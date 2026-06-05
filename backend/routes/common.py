from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, TypeVar

from fastapi import Header, HTTPException, status

from ..models import AnnouncementCreate, AnnouncementUpdate
from ..repository import Member, get_member

TOKEN_TTL_HOURS = 7
ROLE_MEMBER = 'member'
ROLE_ADMIN = 'admin'
ROLE_LEADER = 'leader'
ALLOWED_ROLES = {ROLE_MEMBER, ROLE_ADMIN, ROLE_LEADER}
F = TypeVar('F', bound=Callable[..., Any])


@dataclass(frozen=True)
class CurrentUser:
    id: int
    role: str
    member: Member


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def member_to_public(member: Member) -> dict[str, Any]:
    return member.model_dump(mode='json')


def sanitize_member_payload(payload: Any) -> Any:
    data = payload.model_dump(exclude={'password'}, exclude_unset=False)
    if data.get('role') not in ALLOWED_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='invalid role')
    if data.get('role') != ROLE_MEMBER:
        if payload.__class__.__name__ == 'UserRegister':
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='role escalation is not allowed')
        data['role'] = ROLE_MEMBER
    return data


def token_for_member(member: Member) -> str:
    expires_at = (utcnow() + timedelta(hours=TOKEN_TTL_HOURS)).isoformat()
    return f'{member.id}:{member.role}:{expires_at}'


def parse_token(token: str) -> CurrentUser:
    try:
        member_id_str, role, expires_at_str = token.split(':', 2)
        member_id = int(member_id_str)
        expires_at = datetime.fromisoformat(expires_at_str)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token') from exc

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')

    member = get_member(member_id)
    if member is None or member.role != role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid or expired token')
    return CurrentUser(id=member.id, role=member.role, member=member)


def get_current_user(authorization: str | None = Header(default=None, alias='Authorization')) -> CurrentUser:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='missing bearer token')
    return parse_token(authorization.removeprefix('Bearer ').strip())


def get_optional_current_user(authorization: str | None = Header(default=None, alias='Authorization')) -> CurrentUser | None:
    if not authorization:
        return None
    return get_current_user(authorization)


def require_roles(*roles: str):
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            current_user = kwargs.pop('current_user')
            if current_user.role not in roles:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='forbidden')
            return func(*args, current_user=current_user, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def admin_or_leader(current_user: CurrentUser | None) -> None:
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='missing bearer token')
    if current_user.role not in {ROLE_ADMIN, ROLE_LEADER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='forbidden')


def member_read_guard(member_id: int, current_user: CurrentUser) -> None:
    if current_user.role in {ROLE_ADMIN, ROLE_LEADER}:
        return
    if current_user.id != member_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='forbidden')


def member_write_guard(member_id: int, current_user: CurrentUser) -> None:
    if current_user.role in {ROLE_ADMIN, ROLE_LEADER}:
        return
    if current_user.id != member_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='forbidden')


def registration_member_guard(member_id: int, current_user: CurrentUser | None) -> None:
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='missing bearer token')
    if current_user.role in {ROLE_ADMIN, ROLE_LEADER}:
        return
    if current_user.id != member_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='forbidden')


def announcement_payload(payload: AnnouncementCreate | AnnouncementUpdate) -> dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    if 'content' in data and 'body' not in data:
        data['body'] = data.pop('content')
    if 'body' in data and 'content' not in data:
        data['content'] = data['body']
    data.pop('content', None)
    data['is_pinned'] = True
    return data
