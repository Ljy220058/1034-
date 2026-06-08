from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app
from backend.routes.achievements import ACHIEVEMENT_RULES, evaluate_achievements

client = TestClient(app)


def test_evaluate_achievements_rules_pure_function() -> None:
    payload = {
        'total_distance_km': 120,
        'consecutive_checkin_days': 7,
        'current_month_attendance_days': 15,
        'activity_count': 10,
    }

    results = evaluate_achievements(payload)

    assert len(results) == 5
    assert all(item['achieved'] is True for item in results)
    assert [item['key'] for item in results] == [rule.key for rule in ACHIEVEMENT_RULES]


def test_evaluate_achievements_rules_with_threshold_edges() -> None:
    payload = {
        'total_distance_km': 9,
        'consecutive_checkin_days': 6,
        'current_month_attendance_days': 14,
        'activity_count': 9,
    }

    results = evaluate_achievements(payload)

    assert results[0]['achieved'] is False
    assert results[1]['achieved'] is False
    assert results[2]['achieved'] is False
    assert results[3]['achieved'] is False
    assert results[4]['achieved'] is False
    assert [item['threshold'] for item in results] == [10, 7, 15, 100, 10]


def test_get_sample_achievements_returns_api_response() -> None:
    response = client.get('/api/v1/achievements/sample')

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已返回成就样例定义'
    assert 'rules' in payload['data']
    assert len(payload['data']['rules']) == 5
    assert [rule['threshold'] for rule in payload['data']['rules']] == [10, 7, 15, 100, 10]
    assert payload['data']['rules'][0]['name'] == '入门跑者'
    assert payload['data']['rules'][4]['source'] == '参与活动数'
