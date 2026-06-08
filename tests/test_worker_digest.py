from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app
from backend.worker_board import list_task_health_rows, upsert_workspace_task_item

client = TestClient(app)


def _auth_headers() -> dict[str, str]:
    return {'Authorization': 'Bearer test-token'}


def _prepare_workspace() -> str:
    workspace_path = '/tmp/hermes-worker-digest-workspace'
    from backend.repository import reset_database

    reset_database()
    upsert_workspace_task_item(
        workspace_path=workspace_path,
        task_key='task-ready',
        title='空闲任务汇总',
        status='todo',
        description='空闲任务说明',
        assignee='张三',
        priority=1,
    )
    upsert_workspace_task_item(
        workspace_path=workspace_path,
        task_key='task-running',
        title='进行中任务汇总',
        status='doing',
        description='进行中任务说明',
        assignee='李四',
        priority=2,
    )
    upsert_workspace_task_item(
        workspace_path=workspace_path,
        task_key='task-blocked',
        title='阻塞任务汇总',
        status='blocked',
        description='阻塞任务说明',
        assignee='王五',
        priority=3,
    )
    upsert_workspace_task_item(
        workspace_path=workspace_path,
        task_key='task-done',
        title='已完成任务汇总',
        status='done',
        description='已完成任务说明',
        assignee='赵六',
        priority=4,
    )
    upsert_workspace_task_item(
        workspace_path=workspace_path,
        task_key='task-ready',
        title='空闲任务汇总更新',
        status='todo',
        description='空闲任务说明更新',
        assignee='张三',
        priority=1,
    )
    list_task_health_rows(workspace_path)
    return workspace_path


def test_worker_board_and_digest_return_structured_api_response() -> None:
    """Worker board endpoints should return the standard API response shape.

    Returns:
        None.
    """
    workspace_path = _prepare_workspace()
    headers = _auth_headers()

    board_response = client.get('/api/v1/workers/board', headers=headers)
    digest_response = client.get('/api/v1/workers/digest', headers=headers)
    health_response = client.get('/api/v1/workers/health', headers=headers)

    assert board_response.status_code == 200
    assert digest_response.status_code == 200
    assert health_response.status_code == 200

    board_payload = board_response.json()
    digest_payload = digest_response.json()
    health_payload = health_response.json()

    assert board_payload['message'] == '成功'
    assert digest_payload['message'] == '成功'
    assert health_payload['message'] == '成功'

    assert 'data' in board_payload and 'data' in digest_payload and 'data' in health_payload
    assert board_payload['data']['workspace_path'] == workspace_path
    assert digest_payload['data']['snapshot']['workspace_path'] == workspace_path
    assert digest_payload['data']['summary']['worker_count'] >= 0
    assert digest_payload['data']['summary']['ready'] == 1
    assert digest_payload['data']['summary']['running'] == 1
    assert digest_payload['data']['summary']['blocked'] == 1
    assert digest_payload['data']['summary']['done'] == 1
    assert isinstance(digest_payload['data']['summary']['duplicate_task_keys'], list)
    assert isinstance(health_payload['data'], list)


def test_worker_digest_hides_health_rows_when_disabled() -> None:
    """Worker digest should support omitting health rows.

    Returns:
        None.
    """
    _prepare_workspace()
    response = client.get('/api/v1/workers/digest?include_health=false', headers=_auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload['data']['health_rows'] == []
    assert payload['data']['summary']['task_health_count'] == 0
