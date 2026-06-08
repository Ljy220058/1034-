from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app, raise_server_exceptions=False)


def test_achievement_sample_returns_api_response() -> None:
    """成就样例接口应返回 ApiResponse 结构。"""
    response = client.get('/api/v1/achievements/sample')

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {'data', 'message'}
    assert body['message'] == '成就规则样例获取成功'
    assert set(body['data'].keys()) == {'rules', 'summary'}
    assert body['data']['summary']['count'] == 5
    assert body['data']['summary']['note'] == '成就规则为纯函数定义，不依赖数据库。'
    assert [item['key'] for item in body['data']['rules']] == [
        'entry_runner',
        'streak_star',
        'monthly_soldier',
        'distance_master',
        'activity_pioneer',
    ]
    assert all('metric' in item and 'threshold' in item for item in body['data']['rules'])
