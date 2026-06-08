from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
from backend.database import connect
from backend.db import initialize_database
from backend.task_board_models import ensure_task_board_schema
from backend.worker_board import build_worker_board_snapshot, upsert_task_queue_worker


def _prepare_workspace(tmp_path: Path) -> str:
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    initialize_database()
    ensure_task_board_schema()
    return str(workspace.resolve())


def _seed_workspace_items(workspace_path: str) -> None:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO workspace_task_items (
                workspace, task_key, title, status, description, assignee, priority, updated_at, metadata, task_id, parent_task_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
            """,
            (
                workspace_path,
                'task-items-001',
                '补充 worker 推荐可见的创意任务',
                'todo',
                '创建一条通过 tasks/items 写入的任务，供推荐接口读取。',
                '张三',
                9,
                '{}',
                'task-item-id-001',
                None,
            ),
        )
        connection.execute(
            """
            INSERT INTO workspace_tasks (
                workspace, task_key, title, status, assignee, priority, updated_at, metadata, task_id, parent_task_id
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
            """,
            (
                workspace_path,
                'task-board-001',
                '来自 workspace_tasks 的回退任务',
                'todo',
                '李四',
                4,
                '{"source":"workspace_tasks"}',
                'task-board-id-001',
                None,
            ),
        )


def test_workspace_task_items_endpoint_reads_tasks_items(tmp_path: Path) -> None:
    workspace_path = _prepare_workspace(tmp_path)
    _seed_workspace_items(workspace_path)

    client = TestClient(app)
    response = client.get(
        '/api/v1/workspaces/tasks/items',
        params={'workspace_path': workspace_path, 'limit': 10},
        headers={'Authorization': 'Bearer leader-token'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['workspace_path'] == workspace_path
    assert len(payload['data']['items']) == 1
    assert payload['data']['items'][0]['task_key'] == 'task-items-001'
    assert payload['data']['items'][0]['assignee'] == '张三'


def test_idle_worker_recommendations_include_items_created_via_tasks_items(tmp_path: Path) -> None:
    workspace_path = _prepare_workspace(tmp_path)
    _seed_workspace_items(workspace_path)
    upsert_task_queue_worker(worker_key='worker-zhangsan', name='张三', status='active', capabilities=['fastapi'])

    client = TestClient(app)
    response = client.get(
        '/api/v1/workers/recommendations',
        params={'workspace_path': workspace_path, 'limit': 10},
        headers={'Authorization': 'Bearer leader-token'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert any(item['source'] == 'workspace_task_items' for item in payload['data']['items'])
    assert any(item['task_key'] == 'task-items-001' for item in payload['data']['items'])


def test_worker_board_snapshot_reads_workspace_task_items(tmp_path: Path) -> None:
    workspace_path = _prepare_workspace(tmp_path)
    _seed_workspace_items(workspace_path)
    upsert_task_queue_worker(worker_key='worker-zhangsan', name='张三', status='active', capabilities=['fastapi'])

    snapshot = build_worker_board_snapshot(workspace_path)
    dumped = snapshot.model_dump(mode='json')

    assert dumped['workspace_path'] == workspace_path
    assert any(item['task_key'] == 'task-items-001' for item in dumped['recent_tasks'])
