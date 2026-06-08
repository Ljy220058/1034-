from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app


client = TestClient(app, raise_server_exceptions=False)


def test_member_ranking_endpoint_returns_api_response() -> None:
    """成员排行接口应返回统一 API 响应。"""
    response = client.get('/api/v1/members/ranking')

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '成员跑量排行获取成功'
    assert isinstance(body['data'], list)
    if body['data']:
        first = body['data'][0]
        assert {'member_id', 'member_name', 'total_distance_km', 'signed_in_activities', 'monthly_distance_km', 'checkin_days', 'average_pace_score'} <= set(first)


def test_member_statistics_endpoint_returns_structured_error_for_missing_member() -> None:
    """成员统计接口在成员不存在时应返回中文结构化错误。"""
    response = client.get('/api/v1/members/ranking/999999')

    assert response.status_code == 404
    assert response.json() == {'detail': '成员不存在'}


def test_member_statistics_endpoint_returns_api_response_for_existing_member() -> None:
    """成员统计接口应返回单个成员的统计信息。"""
    response = client.get('/api/v1/members/ranking/1')

    assert response.status_code in {200, 404}
    if response.status_code == 200:
        body = response.json()
        assert body['message'] == '成员统计获取成功'
        assert {'member_id', 'member_name', 'monthly_distance_km', 'checkin_days', 'average_pace_score'} <= set(body['data'])
