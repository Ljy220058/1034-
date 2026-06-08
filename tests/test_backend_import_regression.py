from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

import backend
import backend.database as database
from backend.app import app
from backend.repository import create_member
from backend.routes.common import token_for_member


def test_backend_package_imports_after_registering_routes(tmp_path: Path) -> None:
    """Backend package should import successfully after route registration.

    Args:
        tmp_path: Temporary pytest directory.

    Returns:
        None.
    """
    database.init_db(tmp_path / 'backend_import.db')
    result = subprocess.run(
        [sys.executable, '-c', 'import backend; print(backend.app.title)'],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert '1034 Running Club API' in result.stdout


def test_activities_create_endpoint_imports_and_responds(tmp_path: Path) -> None:
    """Activities create endpoint should respond with structured ApiResponse.

    Args:
        tmp_path: Temporary pytest directory.

    Returns:
        None.
    """
    database.init_db(tmp_path / 'activities.db')
    client = TestClient(app, raise_server_exceptions=False)
    leader_id = create_member(name='Leader', phone='13800000002', role='leader', password='secret123')
    leader = type('Leader', (), {'id': leader_id, 'role': 'leader'})()
    token = token_for_member(leader)
    response = client.post(
        '/api/v1/activities',
        json={
            'title': '晨跑',
            'start_time': '2026-06-01T07:00:00+00:00',
            'location': '西湖',
            'distance_km': 8.8,
        },
        headers={'Authorization': f'Bearer {token}'},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['title'] == '晨跑'
