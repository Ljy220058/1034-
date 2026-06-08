from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app, raise_server_exceptions=False)



def test_training_plan_export_returns_structured_api_payload() -> None:
    """训练计划 ICS 导出接口应返回结构化响应。"""
    response = client.post(
        '/api/v1/training-plan/export',
        json={
            'activities': [
                {
                    'title': '周末长距离训练',
                    'start_time': '2026-06-07T07:00:00+08:00',
                    'end_time': '2026-06-07T09:00:00+08:00',
                    'location': '奥森南园',
                    'description': '配速 6:00，完成后拉伸',
                    'activity_url': 'https://run.example.com/activities/42',
                }
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        'data': {
            'config_path': '/root/autodl-tmp/projects/hermes-swarm-lab/data/training_plan.json',
            'export_name': 'training-plan.ics',
            'mime_type': 'text/calendar; charset=utf-8',
            'content': body['data']['content'],
            'activity_count': 1,
        },
        'message': '已生成训练计划 ICS 导出内容',
    }
    assert body['data']['content'].startswith('BEGIN:VCALENDAR\r\nVERSION:2.0\r\n')
    assert 'SUMMARY:周末长距离训练' in body['data']['content']
    assert 'DTSTART:20260606T230000Z' in body['data']['content']
    assert 'DTEND:20260607T010000Z' in body['data']['content']


def test_training_plan_export_rejects_non_array_activities() -> None:
    """activities 不是数组时应返回结构化错误。"""
    response = client.post('/api/v1/training-plan/export', json={'activities': {}})

    assert response.status_code == 400
    assert response.json() == {'detail': 'activities 必须是数组'}


def test_training_plan_export_rejects_missing_title() -> None:
    """缺少标题时应返回结构化错误。"""
    response = client.post(
        '/api/v1/training-plan/export',
        json={
            'activities': [
                {
                    'title': '  ',
                    'start_time': '2026-06-07T07:00:00+08:00',
                    'end_time': '2026-06-07T09:00:00+08:00',
                }
            ]
        },
    )

    assert response.status_code == 400
    assert response.json() == {'detail': 'title 不能为空'}


def test_training_plan_export_rejects_end_before_start() -> None:
    """结束时间早于开始时间时应返回结构化错误。"""
    response = client.post(
        '/api/v1/training-plan/export',
        json={
            'activities': [
                {
                    'title': '反向训练',
                    'start_time': '2026-06-07T09:00:00+08:00',
                    'end_time': '2026-06-07T07:00:00+08:00',
                }
            ]
        },
    )

    assert response.status_code == 400
    assert response.json() == {'detail': 'end_time 不能早于 start_time'}
