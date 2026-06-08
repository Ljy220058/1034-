from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app, raise_server_exceptions=False)



def _seed_checkin_stats_fixture() -> None:
    import backend.database as database

    today = date.today()
    month_day = today - timedelta(days=2)
    streak_day_1 = today - timedelta(days=1)
    streak_day_2 = today
    old_longest_start = today - timedelta(days=10)
    old_longest_day_1 = old_longest_start
    old_longest_day_2 = old_longest_start + timedelta(days=1)
    old_longest_day_3 = old_longest_start + timedelta(days=2)

    with database.connect() as connection:
        connection.execute('DELETE FROM attendances')
        connection.execute('DELETE FROM members')
        connection.execute('DELETE FROM activities')
        connection.execute(
            'INSERT INTO members(id, name, phone, role, running_years, pace, usual_distance_km, training_goal, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (1, 'Alice', '13800000001', 'member', 3, '5:30', 8.0, 'keep running', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'),
        )
        for activity_id, start_date in enumerate([month_day, streak_day_1, streak_day_2, old_longest_day_1, old_longest_day_2, old_longest_day_3], start=1):
            connection.execute(
                'INSERT INTO activities(id, title, start_time, location, route, distance_km, pace_group, description, max_participants, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    activity_id,
                    f'Run {activity_id}',
                    datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
                    'Park',
                    None,
                    5.0,
                    None,
                    None,
                    20,
                    '2026-01-01T00:00:00+00:00',
                    '2026-01-01T00:00:00+00:00',
                ),
            )
        attendance_dates = [month_day, streak_day_1, streak_day_2, old_longest_day_1, old_longest_day_2, old_longest_day_3]
        for attendance_id, (activity_id, signed_date) in enumerate(zip(range(1, 7), attendance_dates, strict=True), start=1):
            signed_at = datetime.combine(signed_date, datetime.min.time(), tzinfo=timezone.utc).isoformat()
            connection.execute(
                'INSERT INTO attendances(id, activity_id, member_id, status, signed_in_at, gps_checked, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (attendance_id, activity_id, 1, 'signed_in', signed_at, 1, signed_at),
            )



def test_checkin_stats_returns_expected_summary() -> None:
    _seed_checkin_stats_fixture()

    response = client.get('/api/v1/checkin-stats/1')

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '打卡统计获取成功'
    assert body['data']['member_id'] == 1
    assert body['data']['current_streak_days'] == 2
    assert body['data']['longest_streak_days'] == 3
    assert body['data']['checkin_days_this_month'] == 3
    assert len(body['data']['recent_365_days']) == 6



def test_checkin_heatmap_returns_daily_counts() -> None:
    _seed_checkin_stats_fixture()

    response = client.get('/api/v1/checkin-heatmap/1')

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '打卡热力图获取成功'
    assert len(body['data']) == 365
    assert sum(item['count'] for item in body['data']) == 6
    assert any(item['count'] == 1 for item in body['data'])



def test_checkin_stats_returns_structured_error_for_missing_member() -> None:
    response = client.get('/api/v1/checkin-stats/999999')

    assert response.status_code == 404
    assert response.json() == {'detail': '成员不存在'}
