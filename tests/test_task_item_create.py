from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.repository import Member
from backend.routes.common import CurrentUser, get_current_user

client = TestClient(app, raise_server_exceptions=False)


def _leader_user() -> CurrentUser:
    """Build a leader user for route tests.

    Returns:
        A current user instance with leader permissions.
    """
    member = Member(
        id=1,
        name='测试团长',
        phone=None,
        role='leader',
        running_years=3,
        pace=None,
        usual_distance_km=None,
        training_goal=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    return CurrentUser(id=1, role='leader', member=member)


def test_task_item_create_rejects_english_title_with_chinese_error() -> None:
    """Task item creation should reject English-only titles.

    Returns:
        None.
    """
    from backend.models import TaskItemCreate

    with pytest.raises(ValueError, match='标题必须包含中文'):
        TaskItemCreate(
            task_key='creative-1',
            title='English title only',
            description='中文描述，用于校验。',
        )


def test_task_item_create_rejects_english_description_with_chinese_error() -> None:
    """Task item creation should reject English-only descriptions.

    Returns:
        None.
    """
    from backend.models import TaskItemCreate

    with pytest.raises(ValueError, match='描述必须包含中文'):
        TaskItemCreate(
            task_key='creative-2',
            title='中文标题',
            description='English description only',
        )


def test_task_item_create_rejects_blank_assignee_with_chinese_error() -> None:
    """Task item creation should reject blank assignees.

    Returns:
        None.
    """
    from backend.models import TaskItemCreate

    with pytest.raises(ValueError, match='负责人不能为空'):
        TaskItemCreate(
            task_key='creative-3',
            title='中文标题',
            description='中文描述，用于校验。',
            assignee='   ',
        )


def test_task_item_create_requires_assignee_and_reports_chinese_error() -> None:
    """Task item creation should require an assignee and reject missing values.

    Returns:
        None.
    """
    from backend.models import TaskItemCreate

    with pytest.raises(ValueError, match='Field required'):
        TaskItemCreate(
            task_key='creative-4',
            title='中文标题',
            description='中文描述，用于校验。',
        )


def test_task_item_create_endpoint_returns_chinese_error_for_english_title() -> None:
    """API should return a Chinese validation error for an English title.

    Returns:
        None.
    """
    app.dependency_overrides[get_current_user] = _leader_user
    try:
        response = client.post(
            '/api/v1/workspaces/tasks/items',
            json={
                'task_key': 'creative-5',
                'title': 'English title only',
                'description': '中文描述，用于校验。',
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    payload = response.json()
    assert payload['detail'] == '标题必须包含中文'


def test_task_item_create_endpoint_returns_chinese_error_for_english_description() -> None:
    """API should return a Chinese validation error for an English description.

    Returns:
        None.
    """
    app.dependency_overrides[get_current_user] = _leader_user
    try:
        response = client.post(
            '/api/v1/workspaces/tasks/items',
            json={
                'task_key': 'creative-6',
                'title': '中文标题',
                'description': 'English description only',
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    payload = response.json()
    assert payload['detail'] == '描述必须包含中文'


def test_task_item_create_endpoint_returns_chinese_error_for_blank_assignee() -> None:
    """API should return a Chinese validation error for a blank assignee.

    Returns:
        None.
    """
    app.dependency_overrides[get_current_user] = _leader_user
    try:
        response = client.post(
            '/api/v1/workspaces/tasks/items',
            json={
                'task_key': 'creative-7',
                'title': '中文标题',
                'description': '中文描述，用于校验。',
                'assignee': '   ',
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    payload = response.json()
    assert payload['detail'] == '负责人不能为空'
