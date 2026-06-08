from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend
import backend.database as database
from backend.app import app
from backend.repository import create_member_with_password


def test_backend_imports_app_and_repository_exports() -> None:
    """Backend package should expose app and repository helpers.

    Returns:
        None.
    """
    assert backend.app is app
    assert hasattr(backend, 'create_member_with_password')
    assert backend.create_member_with_password is create_member_with_password


def test_backend_imports_and_auth_register_works(tmp_path: Path) -> None:
    """Backend package should import and auth register should work.

    Args:
        tmp_path: Temporary directory from pytest.
    """
    db_path = tmp_path / 'auth.db'
    database.init_db(db_path)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        '/api/v1/auth/register',
        json={'name': '测试用户', 'phone': '15550009999', 'password': 'secret123', 'role': 'member'},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['member']['phone'] == '15550009999'
    assert payload['data']['token_type'] == 'Bearer'
