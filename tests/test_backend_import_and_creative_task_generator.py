from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import app
from conftest import make_auth_headers


def test_backend_import_and_health_endpoints() -> None:
    """验证 backend 可导入且健康检查端点可响应。"""
    assert isinstance(app, FastAPI)

    client = TestClient(app)
    response = client.get('/healthz')

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
    assert 'uptime' in payload
    assert 'version' in payload


def test_creative_task_generator_returns_api_response() -> None:
    """验证创意任务生成接口返回 ApiResponse 结构。"""
    client = TestClient(app)
    response = client.get(
        '/api/v1/idle-backend-task-recommender',
        headers={'Authorization': make_auth_headers(client, '19900000001', 'leader')['Authorization']},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert isinstance(payload['data']['count'], int)
    assert payload['data']['count'] == 2
    assert len(payload['data']['tasks']) == 2
    first_task = payload['data']['tasks'][0]
    assert first_task['title']
    assert first_task['body'].startswith('产出一个 FastAPI') or 'FastAPI' in first_task['body']
    assert first_task['workspace_kind'] == 'dir'
