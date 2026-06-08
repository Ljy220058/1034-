from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, TypeVar

from fastapi import Header, HTTPException, status

from ..models import AnnouncementCreate, AnnouncementUpdate
from ..repository import get_member

TOKEN_TTL_HOURS = 7
JWT_ALGORITHM = 'HS256'
JWT_ISSUER = '1034-running-club'
JWT_AUDIENCE = '1034-api'
ROLE_MEMBER = 'member'
ROLE_ADMIN = 'admin'
ROLE_LEADER = 'leader'
ALLOWED_ROLES = {ROLE_MEMBER, ROLE_ADMIN, ROLE_LEADER}
F = TypeVar('F', bound=Callable[..., Any])


@dataclass(frozen=True)
class CurrentUser:
    id: int
    role: str
    member: Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _jwt_secret() -> str:
    """读取 JWT 签名密钥。

    Returns:
        环境变量中的 JWT 密钥。

    Raises:
        RuntimeError: 未配置密钥时抛出，避免降级为未签名 token。
    """
    secret = os.getenv('RUNNING_CLUB_JWT_SECRET')
    if not secret:
        raise RuntimeError('RUNNING_CLUB_JWT_SECRET is required')
    return secret


def _base64url_encode(raw: bytes) -> str:
    """按 JWT 规范执行 base64url 编码。"""
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def _base64url_decode(value: str) -> bytes:
    """按 JWT 规范执行 base64url 解码。"""
    return base64.urlsafe_b64decode((value + '=' * (-len(value) % 4)).encode('ascii'))


def _jwt_error() -> HTTPException:
    """构造统一认证失败异常。"""
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='未授权或 token 已过期')


def _sign_jwt_part(signing_input: str) -> str:
    """签名 JWT header.payload 部分。

    Args:
        signing_input: JWT header 和 payload 的点号拼接文本。

    Returns:
        base64url 编码后的 HMAC-SHA256 签名。
    """
    digest = hmac.new(_jwt_secret().encode('utf-8'), signing_input.encode('ascii'), hashlib.sha256).digest()
    return _base64url_encode(digest)


def _encode_jwt(payload: dict[str, Any]) -> str:
    """用 HMAC-SHA256 签名 JWT。

    Args:
        payload: JWT 载荷。

    Returns:
        已签名 JWT 字符串。
    """
    header = {'alg': JWT_ALGORITHM, 'typ': 'JWT'}
    header_part = _base64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_part = _base64url_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
    signing_input = f'{header_part}.{payload_part}'
    return f'{signing_input}.{_sign_jwt_part(signing_input)}'


def _decode_jwt(token: str) -> dict[str, Any]:
    """校验并解码 JWT。

    Args:
        token: Bearer token 字符串。

    Returns:
        校验通过后的载荷。

    Raises:
        HTTPException: token 格式、签名或声明无效时返回 401。
    """
    parts = token.split('.')
    if len(parts) != 3:
        raise _jwt_error()
    signing_input = f'{parts[0]}.{parts[1]}'
    if not hmac.compare_digest(parts[2], _sign_jwt_part(signing_input)):
        raise _jwt_error()
    try:
        header = json.loads(_base64url_decode(parts[0]))
        payload = json.loads(_base64url_decode(parts[1]))
    except (ValueError, json.JSONDecodeError) as exc:
        raise _jwt_error() from exc
    if header.get('alg') != JWT_ALGORITHM or header.get('typ') != 'JWT':
        raise _jwt_error()
    if not isinstance(payload, dict):
        raise _jwt_error()
    return payload


def member_to_public(member: Any) -> dict[str, Any]:
    return member.model_dump(mode='json')


def sanitize_member_payload(payload: Any) -> Any:
    data = payload.model_dump(exclude={'password'}, exclude_unset=False)
    if data.get('role') not in ALLOWED_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='invalid role')
    if data.get('role') != ROLE_MEMBER:
        if payload.__class__.__name__ == 'UserRegister':
            # bootstrap: first user can be any role; reject escalation thereafter
            from ..database import connect as _bc
            with _bc() as _bconn:
                _bcnt = _bconn.execute('SELECT COUNT(*) FROM members').fetchone()[0]
            if _bcnt > 0:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='role escalation is not allowed')
        else:
            data['role'] = ROLE_MEMBER
    return data


def token_for_member(member: Any, expires_in_seconds: int | None = None) -> str:
    """为成员签发 HMAC-SHA256 JWT。

    Args:
        member: 成员对象，需包含 id 和 role。
        expires_in_seconds: 可选过期秒数，测试可传负值构造过期 token。

    Returns:
        已签名 JWT 字符串。
    """
    now = utcnow()
    ttl_seconds = expires_in_seconds if expires_in_seconds is not None else TOKEN_TTL_HOURS * 60 * 60
    expires_at = now + timedelta(seconds=ttl_seconds)
    payload = {
        'sub': str(member.id),
        'role': member.role,
        'iss': JWT_ISSUER,
        'aud': JWT_AUDIENCE,
        'iat': int(now.timestamp()),
        'exp': int(expires_at.timestamp()),
    }
    return _encode_jwt(payload)


def parse_token(token: str) -> CurrentUser:
    """校验 Bearer token 并返回当前用户。

    Args:
        token: 已签名 JWT。

    Returns:
        当前用户信息。

    Raises:
        HTTPException: token 无效、过期或成员角色已变化时返回 401。
    """
    payload = _decode_jwt(token)
    try:
        member_id = int(payload['sub'])
        role = str(payload['role'])
        expires_at = int(payload['exp'])
        issuer = str(payload['iss'])
        audience = payload['aud']
    except (KeyError, TypeError, ValueError) as exc:
        raise _jwt_error() from exc

    if issuer != JWT_ISSUER or audience != JWT_AUDIENCE:
        raise _jwt_error()
    if expires_at < int(utcnow().timestamp()):
        raise _jwt_error()
    if role not in ALLOWED_ROLES:
        raise _jwt_error()

    member = get_member(member_id)
    if member is None or member.role != role:
        raise _jwt_error()
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
