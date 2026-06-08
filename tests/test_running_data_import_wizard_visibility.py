from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app import app
from backend.models import ActivityCreate
from backend.repository import create_activity, reset_database
from backend.routes.common import token_for_member


class _Member:
    def __init__(self, member_id: int, role: str) -> None:
        self.id = member_id
        self.role = role


def _auth_header(member_id: int, role: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token_for_member(_Member(member_id, role))}'}


def test_wizard_does_not_count_other_member_private_activity() -> None:
    reset_database()
    create_activity(
        ActivityCreate(
            title='晨跑',
            start_time=datetime(2026, 6, 6, 7, 0, tzinfo=timezone.utc),
            location='公园',
            route='A线',
            distance_km=5,
            pace_group='5:30',
            description='早晨训练',
            max_participants=10,
        )
    )

    client = TestClient(app)
    response = client.post(
        '/api/v1/running-data-imports/wizard',
        json={
            'source': 'generic',
            'format': 'csv',
            'content': '晨跑,2026-06-06 07:00:00,1800,5000,track-a',
        },
        headers=_auth_header(2, 'member'),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['duplicate_count'] == 0


def test_wizard_counts_own_visible_activity() -> None:
    reset_database()
    create_activity(
        ActivityCreate(
            title='晨跑',
            start_time=datetime(2026, 6, 6, 7, 0, tzinfo=timezone.utc),
            location='公园',
            route='A线',
            distance_km=5,
            pace_group='5:30',
            description='早晨训练',
            max_participants=10,
        )
    )

    client = TestClient(app)
    response = client.post(
        '/api/v1/running-data-imports/wizard',
        json={
            'source': 'generic',
            'format': 'csv',
            'content': '晨跑,2026-06-06 07:00:00,1800,5000,track-a',
        },
        headers=_auth_header(1, 'member'),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['data']['duplicate_count'] == 1


def test_wizard_admin_keeps_business_expectation() -> None:
    reset_database()
    create_activity(
        ActivityCreate(
            title='晨跑',
            start_time=datetime(2026, 6, 6, 7, 0, tzinfo=timezone.utc),
            location='公园',
            route='A线',
            distance_km=5,
            pace_group='5:30',
            description='早晨训练',
            max_participants=10,
        )
    )

    client = TestClient(app)
    response = client.post(
        '/api/v1/running-data-imports/wizard',
        json={
            'source': 'generic',
            'format': 'csv',
            'content': '晨跑,2026-06-06 07:00:00,1800,5000,track-a',
        },
        headers=_auth_header(1, 'admin'),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['data']['duplicate_count'] == 0
