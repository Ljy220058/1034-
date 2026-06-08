from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app, raise_server_exceptions=False)



def test_member_achievements_returns_earned_and_locked_lists() -> None:
    """成员成就接口应返回已获得和未获得列表。"""
    response = client.get('/api/v1/achievements/1')

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '成员成就获取成功'
    assert body['data']['member_id'] == 1
    assert isinstance(body['data']['earned'], list)
    assert isinstance(body['data']['locked'], list)
    assert len(body['data']['earned']) >= 2
    assert len(body['data']['locked']) >= 1



def test_member_achievements_not_found_returns_structured_error() -> None:
    """成员不存在时应返回中文结构化错误。"""
    response = client.get('/api/v1/achievements/999999')

    assert response.status_code == 404
    assert response.json() == {'detail': '成员不存在'}



def test_achievement_leaderboard_orders_by_achievement_count() -> None:
    """成就排行榜应按成就数量排序。"""
    response = client.get('/api/v1/achievements/leaderboard')

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '成就排行榜获取成功'
    rows = body['data']
    assert [row['member_id'] for row in rows[:2]] == [1, 2]
    assert rows[0]['achievement_count'] >= rows[1]['achievement_count']
    assert rows[0]['earned_achievements'] == ['rookie_runner', 'social_runner', 'early_member']



def test_achievement_routes_exposed_in_openapi() -> None:
    """成就路径应注册到应用。"""
    response = client.get('/openapi.json')

    assert response.status_code == 200
    paths = response.json()['paths']
    assert '/api/v1/achievements/{member_id}' in paths
    assert '/api/v1/achievements/leaderboard' in paths
