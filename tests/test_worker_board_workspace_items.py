from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
from backend.database import connect
from backend.db import initialize_database
from backend.repository import upsert_workspace_task_item



def _prepare_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    return workspace


def test_worker_board_includes_workspace_task_items(tmp_path: Path, monkeypatch) -> None:
    """Worker board should surface tasks created via /api/v1/workspaces/tasks/items.

    Args:
        tmp_path: Pytest temp directory.
        monkeypatch: Pytest monkeypatch helper.
    """
    workspace = _prepare_workspace(tmp_path)
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(workspace))
    initialize_database()
    upsert_workspace_task_item(
        workspace_path=workspace,
        task_key='creative-001',
        title='创建创意任务',
        status='todo',
        description='来自 tasks/items 创建的新创意任务',
        assignee='idle-worker-a',
        priority=7,
        metadata={'source': 'tasks/items'},
    )

    response = TestClient(app).get('/api/v1/workers/board', params={'workspace_path': str(workspace)})

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['workspace_path'] == str(workspace.resolve())
    recent_tasks = payload['data']['recent_tasks']
    assert any(task['task_key'] == 'creative-001' for task in recent_tasks)
    created = next(task for task in recent_tasks if task['task_key'] == 'creative-001')
    assert created['title'] == '创建创意任务'
    assert created['metadata']['source'] == 'tasks/items'


def test_worker_board_merges_workspace_tasks_and_items(tmp_path: Path, monkeypatch) -> None:
    """Worker board should merge legacy workspace_tasks and workspace_task_items.

    Args:
        tmp_path: Pytest temp directory.
        monkeypatch: Pytest monkeypatch helper.
    """
    workspace = _prepare_workspace(tmp_path)
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(workspace))
    initialize_database()

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO workspace_tasks(workspace, task_key, title, status, assignee, priority, updated_at, metadata, task_id, parent_task_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(workspace.resolve()),
                'legacy-001',
                '旧表任务',
                'todo',
                'idle-worker-b',
                5,
                '2026-06-06T00:00:00+00:00',
                '{"description": "legacy"}',
                'legacy-001',
                None,
            ),
        )

    upsert_workspace_task_item(
        workspace_path=workspace,
        task_key='item-001',
        title='新表任务',
        status='doing',
        description='来自 workspace_task_items 的任务',
        assignee='idle-worker-c',
        priority=9,
        metadata={'source': 'workspace_task_items'},
    )

    response = TestClient(app).get('/api/v1/workers/board', params={'workspace_path': str(workspace)})

    assert response.status_code == 200
    tasks = response.json()['data']['recent_tasks']
    task_keys = {task['task_key'] for task in tasks}
    assert {'legacy-001', 'item-001'} <= task_keys
    legacy = next(task for task in tasks if task['task_key'] == 'legacy-001')
    assert legacy['description'] == 'legacy'
    assert legacy['status'] == 'todo'
