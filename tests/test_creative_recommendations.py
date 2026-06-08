from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_creative_recommendations_returns_three_items() -> None:
    response = client.get('/api/v1/idle-backend-task-recommender', params={'keywords': '跑团 活动'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已生成创意推荐'
    assert payload['data']['keywords'] == ['跑团', '活动']
    assert len(payload['data']['ideas']) == 3
    for item in payload['data']['ideas']:
        assert isinstance(item['title'], str)
        assert isinstance(item['executability'], int)
        assert isinstance(item['dependencies'], list)
        assert isinstance(item['priority'], int)


def test_creative_recommendations_rejects_blank_keywords() -> None:
    response = client.get('/api/v1/idle-backend-task-recommender', params={'keywords': '   '})

    assert response.status_code == 422
    assert response.json() == {'detail': '关键词不能为空'}


def test_creative_recommendations_sample_is_ok() -> None:
    response = client.get('/api/v1/idle-backend-task-recommender/sample')

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已生成创意推荐'
    assert len(payload['data']['ideas']) == 3
