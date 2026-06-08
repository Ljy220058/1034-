from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app, raise_server_exceptions=False)


def test_idle_worker_recommendations_returns_api_response() -> None:
    """空闲 worker 推荐接口应返回结构化 ApiResponse。"""
    response = client.get('/api/v1/workers/idle-recommendations')

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {'data', 'message'}
    assert body['message'] == '已生成空闲 worker 可执行推荐'
    assert set(body['data'].keys()) == {'workspace_path', 'summary', 'recommendations', 'tasks', 'snapshot'}
    assert isinstance(body['data']['recommendations'], list)
    assert len(body['data']['recommendations']) == 2
    assert all(item['title'].startswith('中文创意：') for item in body['data']['recommendations'])
    assert all('description' in item for item in body['data']['recommendations'])
    assert all('assignee_profile' not in item for item in body['data']['recommendations'])


def test_idle_worker_recommendations_are_stable_for_explicit_workspace() -> None:
    """显式工作区路径下应保持稳定输出结构。"""
    response = client.get(
        '/api/v1/workers/idle-recommendations',
        params={'workspace_path': '/root/autodl-tmp/projects/hermes-swarm-lab'},
    )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已生成空闲 worker 可执行推荐'
    assert body['data']['workspace_path'] == '/root/autodl-tmp/projects/hermes-swarm-lab'
    assert all('reason' in item for item in body['data']['recommendations'])
