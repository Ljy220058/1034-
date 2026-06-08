from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.database as database
from backend.routes import register_routes


def test_register_routes_includes_existing_modules_only(tmp_path: Path) -> None:
    """注册入口只应包含真实存在的路由模块。

    Args:
        tmp_path: pytest 提供的临时目录。

    Returns:
        None.
    """
    db_path = tmp_path / 'routes.db'
    database.init_db(db_path)

    app = FastAPI()
    register_routes(app)
    paths = {route.path for route in app.routes}

    assert '/api/v1/login_verification/login' in paths
    assert '/api/v1/login_verification/register' in paths
    assert '/api/v1/training_plan_completion' in paths
    assert '/api/v1/activity_digest' in paths
    assert '/api/v1/attendance' not in paths
    assert '/api/v1/notifications' not in paths
    assert '/api/v1/onboarding' not in paths
    assert '/api/v1/team_snapshots' not in paths
    assert '/api/v1/running_mileage' not in paths
    assert '/api/v1/routes_common' not in paths
    assert '/api/v1/health' not in paths


def test_root_app_still_responds_after_route_registration(tmp_path: Path) -> None:
    """路由重构后应用根路径应继续正常响应。

    Args:
        tmp_path: pytest 提供的临时目录。

    Returns:
        None.
    """
    db_path = tmp_path / 'app.db'
    database.init_db(db_path)
    from backend.app import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get('/')
    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '1034 Running Club backend is running. Visit /docs for the API documentation.'
