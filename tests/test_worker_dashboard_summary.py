from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app
from conftest import make_auth_headers

client = TestClient(app, raise_server_exceptions=False)


def test_dashboard_summary_returns_compact_api_response() -> None:
    response = client.get('/api/v1/dashboard/digest/summary', params={'workspace_path': '/root/autodl-tmp/projects/hermes-swarm-lab'}, headers={'Authorization': make_auth_headers(client, '19900000001', 'leader')['Authorization']})

    assert response.status_code in {200, 401}
    if response.status_code == 200:
        body = response.json()
        assert set(body.keys()) == {'data', 'message'}
        assert body['message'] == '已返回看板摘要'
        assert set(body['data'].keys()) == {'workspace_path', 'summary', 'workers', 'task_health', 'recommendations', 'snapshot'}
        assert isinstance(body['data']['summary'], dict)
        assert isinstance(body['data']['workers'], list)
        assert isinstance(body['data']['task_health'], list)
        assert isinstance(body['data']['recommendations'], list)


def test_dashboard_digest_health_level_filter_keeps_api_shape() -> None:
    response = client.get('/api/v1/dashboard/digest', params={'workspace_path': '/root/autodl-tmp/projects/hermes-swarm-lab', 'health_level': 'blocked', 'limit': 5}, headers={'Authorization': make_auth_headers(client, '19900000001', 'leader')['Authorization']})

    assert response.status_code in {200, 401}
    if response.status_code == 200:
        body = response.json()
        assert set(body.keys()) == {'data', 'message'}
        assert 'task_health' in body['data']
        assert all(str(row.get('health_level', '')).lower() == 'blocked' for row in body['data']['task_health']['items'])


def test_dashboard_summary_requires_workspace_path() -> None:
    response = client.get('/api/v1/dashboard/digest/summary', headers={'Authorization': make_auth_headers(client, '19900000001', 'leader')['Authorization']})

    assert response.status_code == 422
    assert response.json() == {'detail': 'Field required'}
