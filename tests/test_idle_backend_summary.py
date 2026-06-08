from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_idle_worker_summary_returns_structured_json() -> None:
    """空闲 worker 摘要接口应返回结构化 JSON。"""
    response = client.get('/api/v1/workers/idle-summary')

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {'data', 'message'}
    assert body['message'] == '已返回空闲后端摘要'
    assert isinstance(body['data']['summary'], dict)
    assert isinstance(body['data']['idle_workers'], list)
    assert isinstance(body['data']['pending_tasks'], list)
    assert isinstance(body['data']['recent_block_reasons'], list)
    assert isinstance(body['data']['dispatch_recommendations'], list)
    assert body['data']['summary']['dispatch_recommendations'] == len(body['data']['dispatch_recommendations'])
