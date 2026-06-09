from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routes.training_pace import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_计算训练配速_输入有效_返回四类配速区间():
    """正常输入时返回目标配速和四类训练区间。"""
    # Arrange
    payload = {
        'target_distance_km': 10,
        'target_time_minutes': 50,
        'weekly_mileage_km': 35,
        'experience_level': 'intermediate',
    }

    # Act
    response = client.post('/api/v1/training/pace-zones', json=payload)

    # Assert
    assert response.status_code == 200
    assert response.json()['data']['target_pace'] == '5:00/km'
    assert set(response.json()['data']['zones']) == {'easy_run', 'tempo_run', 'interval_run', 'long_run'}


def test_计算训练配速_周跑量较低_轻松跑区间整体放慢():
    """周跑量低于 15 公里时，轻松跑配速会整体放慢。"""
    # Arrange
    payload = {
        'target_distance_km': 10,
        'target_time_minutes': 50,
        'weekly_mileage_km': 10,
        'experience_level': 'intermediate',
    }

    # Act
    response = client.post('/api/v1/training/pace-zones', json=payload)

    # Assert
    assert response.status_code == 200
    assert response.json()['data']['zones']['easy_run']['min_seconds_per_km'] > 350


def test_计算训练配速_周跑量较高_轻松跑区间整体收紧():
    """周跑量高于 70 公里时，轻松跑配速会略微收紧。"""
    # Arrange
    payload = {
        'target_distance_km': 10,
        'target_time_minutes': 50,
        'weekly_mileage_km': 80,
        'experience_level': 'intermediate',
    }

    # Act
    response = client.post('/api/v1/training/pace-zones', json=payload)

    # Assert
    assert response.status_code == 200
    assert response.json()['data']['zones']['easy_run']['max_seconds_per_km'] < 380


def test_计算训练配速_距离为零_返回422():
    """目标距离为 0 时返回 422 校验错误。"""
    # Arrange
    payload = {
        'target_distance_km': 0,
        'target_time_minutes': 50,
        'weekly_mileage_km': 35,
        'experience_level': 'intermediate',
    }

    # Act
    response = client.post('/api/v1/training/pace-zones', json=payload)

    # Assert
    assert response.status_code == 422
    assert '输入值必须大于 0' in response.text


def test_计算训练配速_经验等级非法_返回422():
    """非法经验等级会被请求体校验拒绝。"""
    # Arrange
    payload = {
        'target_distance_km': 10,
        'target_time_minutes': 50,
        'weekly_mileage_km': 35,
        'experience_level': 'expert',
    }

    # Act
    response = client.post('/api/v1/training/pace-zones', json=payload)

    # Assert
    assert response.status_code == 422
    assert response.json()['detail'][0]['loc'][-1] == 'experience_level'


def test_计算训练配速_缺少必填字段_返回422():
    """缺少必填字段时返回 422。"""
    # Arrange
    payload = {'target_distance_km': 10, 'target_time_minutes': 50}

    # Act
    response = client.post('/api/v1/training/pace-zones', json=payload)

    # Assert
    assert response.status_code == 422
    assert any(item['loc'][-1] == 'weekly_mileage_km' for item in response.json()['detail'])
