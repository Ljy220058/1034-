from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app


def test_training_pace_endpoint_returns_api_response() -> None:
    """配速区间接口应返回统一 API 响应。"""
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        '/api/v1/training/pace-zones',
        json={
            'target_distance_km': 10,
            'target_time_minutes': 50,
            'weekly_mileage_km': 35,
            'experience_level': 'advanced',
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '配速区间计算完成'
    assert body['data']['target_pace'] == '5:00/km'
    assert set(body['data']['zones']) == {'easy_run', 'tempo_run', 'interval_run', 'long_run'}
    assert body['data']['zones']['easy_run']['name'] == '轻松跑'


def test_training_pace_endpoint_returns_structured_error_for_invalid_input() -> None:
    """接口无效输入应返回结构化错误。"""
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        '/api/v1/training/pace-zones',
        json={
            'target_distance_km': -1,
            'target_time_minutes': 50,
            'weekly_mileage_km': 35,
            'experience_level': 'advanced',
        },
    )

    assert response.status_code == 422
    assert response.json() == {'detail': '输入值必须大于 0'}


def test_training_pace_endpoint_rejects_invalid_experience_level() -> None:
    """接口应拒绝非法经验等级。"""
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        '/api/v1/training/pace-zones',
        json={
            'target_distance_km': 10,
            'target_time_minutes': 50,
            'weekly_mileage_km': 35,
            'experience_level': 'expert',
        },
    )

    assert response.status_code == 422
    assert response.json() == {'detail': 'Input should be one of beginner, intermediate or advanced'}
