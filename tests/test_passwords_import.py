from __future__ import annotations

from backend.passwords import hash_password, is_strong_password_hash, verify_password


def test_password_helpers_work_without_optional_bcrypt_dependency() -> None:
    """缺少 bcrypt 扩展时密码工具仍可导入并完成基础验证。"""
    password_hash = hash_password('StrongPass123')

    assert is_strong_password_hash(password_hash)
    assert verify_password('StrongPass123', password_hash) is True
    assert verify_password('WrongPass123', password_hash) is False
