from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app
from backend.database import init_db
from backend.repository import create_member


client = TestClient(app)


def _prepare_data() -> int:
    init_db()
    member = create_member(
        {
            'name': '测试成员',
            'phone': '13800000001',
            'role': 'member',
            'running_years': 3,
            'pace': '5:30',
            'usual_distance_km': 10,
            'training_goal': '完成半马',
            'password_hash': '',
        }
    )
    return int(member.id)


def test_export_member_activity_trace_json() -> None:
    member_id = _prepare_data()
    response = client.get(f'/api/v1/members/activity-trace/export?member_id={member_id}&format=json')
    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已导出成员活动轨迹'
    assert 'data' in payload
    assert payload['data']['member']['id'] == member_id
    assert isinstance(payload['data']['activities'], list)
    assert payload['data']['summary']['signed_in_count'] == 0


def test_export_member_activity_trace_csv() -> None:
    member_id = _prepare_data()
    response = client.get(f'/api/v1/members/activity-trace/export?member_id={member_id}&format=csv')
    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已导出成员活动轨迹 CSV'
    assert 'csv' in payload['data']
    assert 'activity_id' in payload['data']['csv']


def test_export_member_activity_trace_invalid_format() -> None:
    member_id = _prepare_data()
    response = client.get(f'/api/v1/members/activity-trace/export?member_id={member_id}&format=xlsx')
    assert response.status_code == 422
    assert response.json() == {'detail': '导出格式仅支持 json 或 csv'}


def test_export_member_activity_trace_date_range_error() -> None:
    member_id = _prepare_data()
    response = client.get(
        f'/api/v1/members/activity-trace/export?member_id={member_id}&start_date=2026-06-10&end_date=2026-06-01',
    )
    assert response.status_code == 422
    assert response.json() == {'detail': '开始日期不能晚于结束日期'}


def test_export_member_activity_trace_missing_member() -> None:
    response = client.get('/api/v1/members/activity-trace/export?member_id=999999')
    assert response.status_code == 404
    assert response.json() == {'detail': '成员不存在'}
