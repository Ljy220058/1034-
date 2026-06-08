from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app



def test_creative_recommendations_valid_keywords_returns_sorted_ideas() -> None:
    """创意推荐在有效关键词下返回按可执行度排序的三条建议。"""
    with TestClient(app) as client:
        response = client.get('/api/v1/creative/recommendations', params={'keywords': '跑团 训练 活动'})

    assert response.status_code == 200
    body = response.json()['data']
    assert body['keywords'] == ['跑团', '训练', '活动']
    assert [item['priority'] for item in body['ideas']] == [1, 2, 3]
    assert body['ideas'][0]['executability'] >= body['ideas'][1]['executability'] >= body['ideas'][2]['executability']



def test_creative_recommendations_missing_keywords_returns_422() -> None:
    """创意推荐缺少 keywords 参数时返回 422。"""
    with TestClient(app) as client:
        response = client.get('/api/v1/creative/recommendations')

    assert response.status_code == 422
    assert response.json()['detail'] == 'Field required'



def test_creative_recommendations_blank_keywords_returns_business_422() -> None:
    """创意推荐传入空白关键词时返回业务 422。"""
    with TestClient(app) as client:
        response = client.get('/api/v1/creative/recommendations', params={'keywords': '   '})

    assert response.status_code == 422
    assert response.json()['detail'] == '关键词不能为空'



def test_creative_recommendations_sample_returns_default_topic_keywords() -> None:
    """创意推荐示例接口返回默认主题关键词。"""
    with TestClient(app) as client:
        response = client.get('/api/v1/creative/recommendations/sample')

    assert response.status_code == 200
    assert response.json()['data']['keywords'] == ['跑团', '训练', '活动']



def test_healthz_returns_ok_and_version() -> None:
    """健康检查接口返回服务状态与版本号。"""
    with TestClient(app) as client:
        response = client.get('/healthz')

    assert response.status_code == 200
    assert response.json()['status'] == 'ok'
    assert 'version' in response.json()
