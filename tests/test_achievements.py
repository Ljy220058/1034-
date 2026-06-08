from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app


def test_sample_achievements_returns_api_response() -> None:
    """成就样例接口返回 ApiResponse 结构。"""
    client = TestClient(app)

    response = client.get('/api/v1/achievements/sample')

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '成就规则样例获取成功'
    assert 'data' in body
    assert len(body['data']['earned_example']) == 5
    assert body['data']['earned_example'][0]['name'] == '入门跑者'
    assert body['data']['earned_example'][0]['rule']['metric_key'] == 'beginner_runner'
    assert body['data']['summary']['count'] == 5
