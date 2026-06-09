from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_activity_share_card_returns_png_response() -> None:
    """活动分享卡片接口返回 image/png 响应和 PNG 魔数。"""
    response = client.get('/api/v1/activities/1/share-card', params={'member_id': 2})

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('image/png')
    assert response.content.startswith(b'\x89PNG\r\n\x1a\n')


def test_activity_share_card_validation_error_is_structured_422() -> None:
    """member_id 校验失败时返回结构化 422 错误。"""
    response = client.get('/api/v1/activities/1/share-card', params={'member_id': 0})

    assert response.status_code == 422
    payload = response.json()
    assert isinstance(payload, dict)
    assert list(payload.keys()) == ['detail']
    assert isinstance(payload['detail'], str)
    assert payload['detail']
