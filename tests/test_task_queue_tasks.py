from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
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
        response = client.get('/api/v1/tasks/progress')

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '成功'
    assert body['data']['count'] == 3
    assert body['data']['items'][0]['task_id'] == 1



def test_task_progress_detail_endpoint_不存在任务时返回404(tmp_path: Path) -> None:
    """读取不存在的任务详情时返回 404。"""
    _init_test_db(tmp_path)
    with TestClient(app) as client:
        response = client.get('/api/v1/tasks/progress/999')
    assert response.status_code == 404
    assert response.json() == {'detail': '任务不存在'}



def test_task_progress_simulate_endpoint_rejects_invalid_steps(tmp_path: Path) -> None:
    """模拟任务进度接口对非法 steps 返回 422。"""
    _init_test_db(tmp_path)
    with TestClient(app) as client:
        response = client.post('/api/v1/tasks/progress/simulate', json={'task_id': 1, 'steps': 1})
    assert response.status_code == 422
    assert 'detail' in response.json()
