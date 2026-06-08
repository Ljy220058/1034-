from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from conftest import make_auth_headers

AUTH_HEADERS = None  # Replaced by make_auth_headers(client, ...) at call site
WORKSPACE_PATH = '/root/autodl-tmp/projects/hermes-swarm-lab'


def _client(tmp_path: Path) -> TestClient:
    """Create a test client against an isolated database.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Test client bound to a fresh database.
    """
    database.init_db(tmp_path / 'test.db')
    return TestClient(app, raise_server_exceptions=False)


def _ensure_worker(client: TestClient, worker_key: str) -> None:
    """Create an active worker used by import validation.

    Args:
        client: FastAPI test client.
        worker_key: Worker identifier used by imported tasks.
    """
    response = client.post(
        '/api/v1/workers/intake',
        json={'worker_key': worker_key, 'name': worker_key, 'status': 'active', 'capabilities': ['backend']},
        headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
    )
    assert response.status_code == 201


def test_task_import_items_file_has_valid_python_syntax() -> None:
    """任务导入测试文件应保持可导入。"""
    compile(Path(__file__).read_text(), __file__, 'exec')
