from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app


client = TestClient(app)


def test_routes_registered_once() -> None:
    """FastAPI route registration should happen only once.

    Returns:
        None.
    """
    route_paths = [getattr(route, 'path', None) for route in app.routes]
    assert route_paths.count('/healthz') == 1
    assert route_paths.count('/health') == 1
    assert route_paths.count('/api/v1/members') == 1


def test_root_health_endpoints_still_work() -> None:
    """Root and health endpoints should return successful responses.

    Returns:
        None.
    """
    root_response = client.get('/')
    assert root_response.status_code == 200
    assert root_response.json()['message'].startswith('1034 Running Club backend is running')

    healthz_response = client.get('/healthz')
    assert healthz_response.status_code == 200
    assert healthz_response.json()['status'] == 'ok'


def test_api_response_structure_from_root_endpoint() -> None:
    """Root endpoint should preserve the documented JSON shape.

    Returns:
        None.
    """
    response = client.get('/')
    payload = response.json()
    assert 'message' in payload
    assert isinstance(payload['message'], str)
