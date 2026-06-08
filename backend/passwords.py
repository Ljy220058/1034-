from __future__ import annotations

import base64
import hashlib
import hmac
import os

try:
    import bcrypt
except ModuleNotFoundError:
    bcrypt = None

BCRYPT_PREFIXES = ('$2a$', '$2b$', '$2y$')
PBKDF2_PREFIX = 'pbkdf2_sha256$'
DUMMY_BCRYPT_HASH = b'$2b$12$uVaj4cuCDGndPfFtQN1ak.fN4ibDIwJ9aaAHn.b1NpZ5e/ftom9wO'
PBKDF2_ITERATIONS = 600_000


def _hash_pbkdf2_password(password: str) -> str:
    """使用标准库生成 PBKDF2 密码哈希。

    Args:
        password: 用户输入的明文密码。

    Returns:
        可存入数据库的 PBKDF2 哈希字符串。
    """
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PBKDF2_ITERATIONS)
    salt_value = base64.urlsafe_b64encode(salt).decode('ascii').rstrip('=')
    digest_value = base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')
    return f'{PBKDF2_PREFIX}{PBKDF2_ITERATIONS}${salt_value}${digest_value}'


def hash_password(password: str) -> str:
    """生成密码哈希。

    Args:
        password: 用户输入的明文密码。

    Returns:
        可存入数据库的密码哈希字符串。
    """
    if bcrypt is not None:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
    return _hash_pbkdf2_password(password)


def is_strong_password_hash(password_hash: str | None) -> bool:
    """判断密码哈希是否为当前强哈希格式。

    Args:
        password_hash: 数据库存储的密码哈希。

    Returns:
        强哈希格式返回 True，否则返回 False。
    """
    return bool(password_hash and (password_hash.startswith(BCRYPT_PREFIXES) or password_hash.startswith(PBKDF2_PREFIX)))


def _verify_pbkdf2_password(password: str, password_hash: str) -> bool:
    """验证 PBKDF2 密码哈希。

    Args:
        password: 用户输入的明文密码。
        password_hash: 数据库存储的 PBKDF2 哈希。

    Returns:
        密码匹配返回 True，否则返回 False。
    """
    try:
        _, iterations_text, salt_text, digest_text = password_hash.split('$', 3)
        iterations = int(iterations_text)
        salt = base64.urlsafe_b64decode(salt_text + '=' * (-len(salt_text) % 4))
        expected = base64.urlsafe_b64decode(digest_text + '=' * (-len(digest_text) % 4))
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return hmac.compare_digest(expected, actual)


def verify_password(password: str, password_hash: str | None) -> bool:
    """验证密码。

    Args:
        password: 用户输入的明文密码。
        password_hash: 数据库存储的密码哈希。

    Returns:
        密码匹配返回 True，否则返回 False。
    """
    password_bytes = password.encode('utf-8')
    if not password_hash:
        if bcrypt is not None:
            bcrypt.checkpw(password_bytes, DUMMY_BCRYPT_HASH)
        else:
            hashlib.pbkdf2_hmac('sha256', password_bytes, b'0' * 16, PBKDF2_ITERATIONS)
        return False
    if password_hash.startswith(PBKDF2_PREFIX):
        return _verify_pbkdf2_password(password, password_hash)
    if password_hash.startswith(BCRYPT_PREFIXES):
        if bcrypt is None:
            return False
        try:
            return bcrypt.checkpw(password_bytes, password_hash.encode('utf-8'))
        except ValueError:
            return False
    return verify_legacy_sha256_password(password, password_hash)


def verify_legacy_sha256_password(password: str, password_hash: str | None) -> bool:
    """验证旧版无盐 SHA-256 密码哈希。

    Args:
        password: 用户输入的明文密码。
        password_hash: 数据库存储的旧哈希。

    Returns:
        旧哈希匹配返回 True，否则返回 False。
    """
    if not password_hash:
        return False
    actual = hashlib.sha256(password.encode('utf-8')).hexdigest()
    return hmac.compare_digest(password_hash, actual)
