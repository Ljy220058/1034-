from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_活动分享卡片接口_返回_png_二进制响应() -> None:
    response = client.get('/api/v1/activities/1/share-card', params={'member_id': 2})

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('image/png')
    assert response.content.startswith(b'\x89PNG\r\n\x1a\n')


def test_活动分享卡片接口_非法_member_id_返回结构化422错误() -> None:
    response = client.get('/api/v1/activities/1/share-card', params={'member_id': 0})

    assert response.status_code == 422
    payload = response.json()
    assert isinstance(payload, dict)
    assert 'detail' in payload
    assert isinstance(payload['detail'], str)
