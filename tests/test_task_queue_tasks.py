from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from conftest import make_auth_headers
from backend.repository import upsert_workspace_task_item

PROJECT_ROOT = Path('/root/autodl-tmp/projects/hermes-swarm-lab')


def _init_test_db(tmp_path: Path) -> None:
    """初始化任务看板测试数据库。

    Args:
        tmp_path: pytest 临时目录。
    """
    database.init_db(tmp_path / 'running_club.db')



def test_task_queue_tasks_endpoint_returns_board_tasks(tmp_path: Path) -> None:
    """任务队列列表接口应返回结构化任务数据。"""
    _init_test_db(tmp_path)
    upsert_workspace_task_item(
        workspace_path=PROJECT_ROOT,
        task_key='task-001',
        title='修复任务队列接口',
        status='running',
        description='补齐 /api/v1/workspaces/task-queue/tasks 接口契约。',
        assignee='backend-dev',
        priority=7,
        metadata={'description': '补齐 /api/v1/workspaces/task-queue/tasks 接口契约。'},
    )
    upsert_workspace_task_item(
        workspace_path=PROJECT_ROOT,
        task_key='task-002',
        title='补充任务列表测试',
        status='todo',
        description='增加 task queue tasks 的回归测试。',
        assignee=None,
        priority=3,
        metadata={'description': '增加 task queue tasks 的回归测试。'},
    )
    with TestClient(app) as client:
        response = client.get(
            '/api/v1/workspaces/task-queue/tasks?workspace=current&limit=2',
            headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
        )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '成功'
    assert len(body['data']) == 2
    first = body['data'][0]
    assert first['id'] == 'task-001'
    assert first['title'] == '修复任务队列接口'
    assert first['assignee'] == 'backend-dev'
    assert first['status'] == 'running'
    assert first['priority'] == 7
    assert first['workspace'] == str(PROJECT_ROOT)
    assert first['created_at'] == first['updated_at']



def test_task_queue_tasks_endpoint_rejects_invalid_status_filter(tmp_path: Path) -> None:
    """任务队列列表接口应对非法状态筛选返回结构化错误。"""
    _init_test_db(tmp_path)

    with TestClient(app) as client:
        response = client.get(
            '/api/v1/workspaces/task-queue/tasks?status=invalid',
            headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
        )

    assert response.status_code == 422
    assert response.json() == {'detail': '任务状态筛选参数不合法'}
