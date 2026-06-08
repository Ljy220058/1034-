from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app


def _init_test_db(tmp_path: Path) -> None:
    """初始化测试数据库。

    Args:
        tmp_path: pytest 临时目录。
    """
    database.init_db(tmp_path / 'running_club.db')


def test_training_plan_completion_quality_gate_returns_structured_rules(tmp_path: Path) -> None:
    """质量门禁接口应返回结构化中文规则结果。"""
    _init_test_db(tmp_path)

    payload = {
        'plan_start_date': '2024-02-28',
        'plan_end_date': '2024-03-02',
        'completion_rate': 101.2,
        'attendance_records': [
            {'member_id': 1, 'checked_in_at': '2024-02-29T08:00:00+00:00'},
            {'member_id': 1, 'checked_in_at': '2024-02-29T08:00:00+00:00'},
        ],
        'daily_targets': [
            {'plan_date': '2024-02-28', 'target_distance_km': 5},
            {'plan_date': '2024-02-29', 'target_distance_km': None, 'target_sessions': None},
        ],
    }

    with TestClient(app) as client:
        response = client.post('/api/v1/training-plan/completion-quality-gate', json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已完成训练计划完成率质量门禁检查'
    assert body['data']['total_rules'] == 6
    assert body['data']['failed_rules'] >= 1
    assert body['data']['config_path'].endswith('data/training_plan.json')
    assert any(rule['rule_key'] == 'cross_month_boundary' for rule in body['data']['rules'])
    assert any(rule['rule_key'] == 'duplicate_checkin' for rule in body['data']['rules'])
    assert any(rule['rule_key'] == 'completion_overflow' and not rule['passed'] for rule in body['data']['rules'])
    assert any(rule['rule_key'] == 'privacy_notice' for rule in body['data']['rules'])


def test_training_plan_completion_quality_gate_rejects_invalid_dates(tmp_path: Path) -> None:
    """非法日期应返回结构化错误。"""
    _init_test_db(tmp_path)

    with TestClient(app) as client:
        response = client.post(
            '/api/v1/training-plan/completion-quality-gate',
            json={
                'plan_start_date': 'not-a-date',
                'plan_end_date': '2024-03-02',
                'completion_rate': 10,
                'attendance_records': [],
                'daily_targets': [],
            },
        )

    assert response.status_code == 400
    assert response.json() == {'detail': 'plan_start_date 不是有效的 ISO 日期'}


def test_training_plan_completion_quality_gate_supports_leap_day() -> None:
    """闰日边界应可被正常识别。"""
    with TestClient(app) as client:
        response = client.post(
            '/api/v1/training-plan/completion-quality-gate',
            json={
                'plan_start_date': '2024-02-29',
                'plan_end_date': '2024-02-29',
                'completion_rate': 0,
                'attendance_records': [],
                'daily_targets': [{'plan_date': '2024-02-29', 'target_distance_km': 5}],
            },
        )

    assert response.status_code == 200
    body = response.json()
    leap_rule = next(rule for rule in body['data']['rules'] if rule['rule_key'] == 'leap_day_coverage')
    assert leap_rule['passed'] is True
