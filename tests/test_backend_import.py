from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app


def test_backend_import_succeeds() -> None:
    """验证 backend 包可正常导入。"""
    assert app.title == '1034 Running Club API'


def test_activities_router_imports_and_health_endpoint_works() -> None:
    """验证活动路由可被 app 正常加载。"""
    client = TestClient(app)
    response = client.get('/healthz')

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
