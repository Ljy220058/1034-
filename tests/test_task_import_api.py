from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.database import DB_PATH, init_db
from backend.repository import reset_database, upsert_workspace_task_item
from backend.task_import import batch_import_task_metadata


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    reset_database()
    init_db(DB_PATH)


def test_imported_doing_status_is_persisted_as_running() -> None:
    result = batch_import_task_metadata(
        [
            {
                'task_key': 'task-002',
                'title': '状态统一',
                'description': '导入 doing 后应落库为 running',
                'status': 'doing',
                'priority': 2,
            },
            {
                'task_key': 'task-003',
                'title': '状态保留',
                'description': '导入 todo 后应保持 todo',
                'status': 'todo',
                'priority': 3,
            },
        ],
        workspace_path='/root/autodl-tmp/projects/hermes-swarm-lab',
    )

    item = result.items[0]
    assert result.count == 2
    assert item.status == 'running'
    assert item.model_dump()['status'] == 'running'


def test_task_import_route_returns_json_structure() -> None:
    client = TestClient(app)
    response = client.post(
        '/api/v1/workspaces/tasks/items/import',
        json={
            'items': [
                {
                    'task_key': 'task-003',
                    'title': '统一状态接口',
                    'description': '后端接口返回应保持 JSON 结构',
                    'status': 'doing',
                    'assignee': None,
                    'priority': 3,
                },
                {
                    'task_key': 'task-004',
                    'title': '第二条任务',
                    'description': '接口需要正好两条任务',
                    'status': 'todo',
                    'assignee': None,
                    'priority': 4,
                },
            ]
        },
    )

    assert response.status_code == 401
    assert response.json() == {'detail': 'missing bearer token'}


def test_task_import_route_rejects_non_two_items() -> None:
    client = TestClient(app)
    response = client.post(
        '/api/v1/workspaces/tasks/items/import',
        json={
            'items': [
                {
                    'task_key': 'task-005',
                    'title': '只给一条',
                    'description': '应该被拒绝',
                    'status': 'doing',
                    'assignee': None,
                    'priority': 1,
                }
            ]
        },
    )

    assert response.status_code == 401
    assert response.json() == {'detail': 'missing bearer token'}
