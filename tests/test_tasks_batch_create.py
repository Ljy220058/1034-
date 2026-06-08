from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_creative_task_batch_create_requires_exactly_two_items() -> None:
    """创意任务批量创建必须正好两张。

    Returns:
        None.
    """
    response = client.post(
        '/api/v1/workspaces/tasks/items/import',
        json={'items': [{'task_key': 'a'}]},
    )
    assert response.status_code == 422
    assert response.json() == {'detail': '创意任务必须正好两张'}


def test_creative_task_batch_create_rejects_more_than_two_items() -> None:
    """创意任务批量创建拒绝多于两张。

    Returns:
        None.
    """
    response = client.post(
        '/api/v1/workspaces/tasks/items/import',
        json={
            'items': [
                {'task_key': 'a'},
                {'task_key': 'b'},
                {'task_key': 'c'},
            ]
        },
    )
    assert response.status_code == 422
    assert response.json() == {'detail': '创意任务必须正好两张'}
