from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app
from backend.repository import create_member_with_password
from backend.routes.common import token_for_member
from backend.models import MemberCreate, AnnouncementCreate

client = TestClient(app)


def _make_member(role: str = 'member', phone: str = '18800000000'):
    member, _ = create_member_with_password(
        MemberCreate(
            name='测试用户',
            phone=phone,
            role=role,
            running_years=3,
            pace='5:30',
            usual_distance_km=10.0,
            training_goal='测试',
        ),
        'hashed-password',
    )
    assert member is not None
    return member


def test_member_cannot_create_announcement() -> None:
    member = _make_member()
    token = token_for_member(member)
    response = client.post(
        '/api/v1/announcements',
        headers={'Authorization': f'Bearer {token}'},
        json={'title': '公告', 'body': '内容', 'status': 'draft', 'is_pinned': False},
    )
    assert response.status_code == 403
    assert response.json() == {'detail': 'forbidden'}


def test_member_cannot_update_announcement() -> None:
    member = _make_member(phone='18800000001')
    token = token_for_member(member)
    response = client.patch(
        '/api/v1/announcements/1',
        headers={'Authorization': f'Bearer {token}'},
        json={'title': '公告', 'body': '内容'},
    )
    assert response.status_code == 403
    assert response.json() == {'detail': 'forbidden'}


def test_member_cannot_delete_announcement() -> None:
    member = _make_member(phone='18800000002')
    token = token_for_member(member)
    response = client.delete('/api/v1/announcements/1', headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 403
    assert response.json() == {'detail': 'forbidden'}
