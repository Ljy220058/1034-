from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app
from backend.kanban_helper import build_workspace_scoped_tasks, create_task_payloads

client = TestClient(app, raise_server_exceptions=False)


def test_workspace_scoped_task_helper_builds_exactly_two_tasks() -> None:
    tasks = build_workspace_scoped_tasks()

    assert len(tasks) == 2
    assert [task.assignee for task in tasks] == ['backend-dev', 'backend-dev']
    assert all(task.workspace == '/root/autodl-tmp/projects/hermes-swarm-lab' for task in tasks)
    assert all('dir:/root/autodl-tmp/projects/hermes-swarm-lab' in task.body for task in tasks)


def test_workspace_scoped_task_specs_have_valid_kanban_payloads() -> None:
    payloads = create_task_payloads()

    assert len(payloads) == 2
    assert all(payload['workspace_kind'] == 'dir' for payload in payloads)
    assert all(payload['workspace_path'] == '/root/autodl-tmp/projects/hermes-swarm-lab' for payload in payloads)
    assert [payload['title'] for payload in payloads] == [
        'Backend: add workspace-scoped kanban task creation endpoint',
        'Backend: add regression tests for workspace-scoped kanban task creation',
    ]


def test_workspace_scoped_task_creation_endpoint_returns_two_payloads() -> None:
    response = client.post('/api/v1/tasks/workspace-scoped-creation-helper')

    assert response.status_code == 200
    payload = response.json()
    assert payload['count'] == 2
    assert len(payload['tasks']) == 2
    for task in payload['tasks']:
        assert task['workspace_kind'] == 'dir'
        assert task['workspace_path'] == '/root/autodl-tmp/projects/hermes-swarm-lab'
        assert task['assignee'] == 'backend-dev'
