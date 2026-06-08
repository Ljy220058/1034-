from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_workspace_scoped_creation_helper_returns_two_tasks() -> None:
    response = client.get('/api/v1/tasks/workspace-scoped-creation-helper')

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '成功'
    assert body['data']['count'] == 2
    assert len(body['data']['tasks']) == 2
    assert body['data']['tasks'][0]['workspace']


def test_workspace_scoped_creation_helper_response_shape() -> None:
    response = client.get('/api/v1/tasks/workspace-scoped-creation-helper')

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {'data', 'message'}
    assert isinstance(body['data']['tasks'], list)
    assert all('title' in task for task in body['data']['tasks'])


def test_batch_create_requires_exactly_two_items_when_too_few() -> None:
    response = client.post(
        '/api/v1/workspaces/tasks/items/batch',
        json={
            'items': [
                {
                    'task_key': 'task-001',
                    'title': '示例任务一',
                    'status': 'todo',
                    'description': '描述一',
                    'assignee': '张三',
                    'priority': 1,
                }
            ]
        },
    )

    assert response.status_code == 422
    assert response.json() == {'detail': '创意任务必须正好两张'}


    app.dependency_overrides[get_current_user] = _leader_user
    try:
        response = client.post(
            '/api/v1/workspaces/tasks/items/batch',
            json={
                'workspace_path': '/root/autodl-tmp/projects/hermes-swarm-lab',
                'items': [
                    {
                        'task_key': 'task-001',
                        'title': '示例任务一',
                        'status': 'todo',
                        'description': '描述一',
                        'assignee': '张三',
                        'priority': 1,
                    },
                    {
                        'task_key': 'task-002',
                        'title': '示例任务二',
                        'status': 'todo',
                        'description': '描述二',
                        'assignee': '李四',
                        'priority': 2,
                    },
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body['message'] == '成功'
    assert body['data']['count'] == 2
    assert len(body['data']['items']) == 2
    assert all(item['metadata'] for item in body['data']['items'])


def test_batch_create_rejects_invalid_workspace_path() -> None:
    app.dependency_overrides[get_current_user] = _leader_user
    try:
        response = client.post(
            '/api/v1/workspaces/tasks/items/batch',
            json={
                'workspace_path': '/tmp',
                'items': [
                    {
                        'task_key': 'task-001',
                        'title': '示例任务一',
                        'status': 'todo',
                        'description': '描述一',
                        'assignee': '张三',
                        'priority': 1,
                    },
                    {
                        'task_key': 'task-002',
                        'title': '示例任务二',
                        'status': 'todo',
                        'description': '描述二',
                        'assignee': '李四',
                        'priority': 2,
                    },
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {'detail': '工作区路径不合法'}
