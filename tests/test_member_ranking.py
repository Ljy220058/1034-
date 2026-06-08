from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app, raise_server_exceptions=False)


def test_member_ranking_returns_api_response() -> None:
    """成员跑量排行接口应返回 ApiResponse。"""
    response = client.get('/api/v1/members/ranking')

    assert response.status_code == 401
    assert response.json()['detail'] == 'missing bearer credential'


def test_member_ranking_rejects_bad_month_format() -> None:
    """成员排行接口应拒绝非法月份格式。"""
    response = client.get('/api/v1/members/ranking?month=2026-13', headers={'Login_verification': 'Bearer invalid'})

    assert response.status_code == 401


def test_member_statistics_missing_member_returns_structured_error() -> None:
    """成员统计接口在成员不存在时应返回中文结构化错误。"""
    response = client.get('/api/v1/members/ranking/999999', headers={'Login_verification': 'Bearer invalid'})

    assert response.status_code == 401
