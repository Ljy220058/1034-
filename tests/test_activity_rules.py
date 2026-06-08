from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_read_default_activity_rules() -> None:
    response = client.get('/api/v1/activity-rules')
    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已返回默认活动规则配置'
    assert 'rules' in payload['data']
    assert payload['data']['rules'][0]['key'] == 'time-window-public'


def test_validate_activity_rules_config() -> None:
    response = client.post(
        '/api/v1/activity-rules/validate',
        json={
            'rules': [
                {
                    'key': 'rule-visible',
                    'scope': 'visible',
                    'operation': 'visibility',
                    'enabled': True,
                    'audience': 'all',
                    'priority': 10,
                    'conditions': [
                        {'kind': 'time_window', 'operator': 'before', 'value': '2099-01-01T00:00:00+00:00'},
                    ],
                    'metadata': {'name': '活动可见性'},
                },
                {
                    'key': 'rule-eligible',
                    'scope': 'eligible',
                    'operation': 'eligibility',
                    'enabled': True,
                    'audience': 'members',
                    'priority': 5,
                    'conditions': [
                        {'kind': 'labels', 'operator': 'none', 'value': ['blacklist']},
                    ],
                    'metadata': {'name': '报名资格'},
                },
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '规则配置校验通过'
    assert payload['data']['rule_count'] == 2
    assert [rule['key'] for rule in payload['data']['rules']] == ['rule-visible', 'rule-eligible']


def test_validate_activity_rules_config_rejects_duplicate_keys() -> None:
    response = client.post(
        '/api/v1/activity-rules/validate',
        json={
            'rules': [
                {'key': 'dup', 'scope': 'visible', 'operation': 'visibility', 'conditions': []},
                {'key': 'dup', 'scope': 'eligible', 'operation': 'eligibility', 'conditions': []},
            ]
        },
    )
    assert response.status_code == 400
    assert response.json() == {'detail': 'rule.key 不能重复'}


def test_evaluate_activity_rules_visibility_and_eligibility() -> None:
    response = client.post(
        '/api/v1/activity-rules/evaluate',
        json={
            'now': '2025-01-01T12:00:00+00:00',
            'user_id': 8,
            'role': 'member',
            'labels': ['runner', 'morning'],
            'usage_count': 3,
            'priority': 'high',
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已计算活动规则结果'
    assert payload['data']['visible'] is True
    assert payload['data']['eligible'] is True
    assert 'time-window-public' in payload['data']['matched_rules']
    assert payload['data']['blocked_reasons'] == []


def test_evaluate_activity_rules_handles_invalid_payload() -> None:
    response = client.post(
        '/api/v1/activity-rules/validate',
        json={'rules': [{'key': 'bad', 'scope': 'visible', 'operation': 'visibility', 'conditions': [{'kind': 'labels', 'operator': 'any', 'value': 'oops'}]}]},
    )
    assert response.status_code == 400
    assert response.json() == {'detail': 'labels.value 必须是非空字符串数组'}
