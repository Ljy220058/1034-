from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_worker_dashboard_summary_returns_api_response() -> None:
    response = client.get('/api/v1/dashboard/digest/summary', params={'workspace_path': '/root/autodl-tmp/projects/hermes-swarm-lab'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已返回空闲度概览面板'
    assert 'data' in payload
    assert 'summary' in payload['data']
    assert 'workers' in payload['data']


def test_worker_dashboard_sidebar_invalid_status_returns_structured_detail() -> None:
    response = client.get('/api/v1/workers/digest', params={'workspace_path': '/root/autodl-tmp/projects/hermes-swarm-lab', 'status': 'invalid'})
    assert response.status_code == 500
    assert response.json() == {'detail': '服务器内部错误'}


def test_idle_worker_summary_returns_api_response() -> None:
    response = client.get('/api/v1/workers/idle-summary', params={'workspace_path': '/root/autodl-tmp/projects/hermes-swarm-lab'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已返回空闲后端摘要'
    assert 'data' in payload
    assert 'idle_workers' in payload['data']
    assert 'dispatch_recommendations' in payload['data']


def test_worker_routing_recommendations_returns_api_response() -> None:
    response = client.get('/api/v1/workers/recommendations', params={'workspace_path': '/root/autodl-tmp/projects/hermes-swarm-lab'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已返回轻量级路由提醒'
    assert 'data' in payload
    assert 'recommendations' in payload['data']
    assert 'summary' in payload['data']
