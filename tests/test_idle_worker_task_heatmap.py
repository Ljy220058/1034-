from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import create_task_queue_worker


def _init_test_db(tmp_path: Path) -> None:
    """初始化空闲 worker 热度图测试数据库。"""
    database.init_db(tmp_path / 'running_club.db')


def _insert_task(workspace: Path, task_key: str, status: str, assignee: str | None, priority: int) -> None:
    """写入工作区任务队列记录。"""
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO workspace_tasks (workspace, task_key, title, status, assignee, priority, metadata, task_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(workspace.resolve()),
                task_key,
                f'中文任务 {task_key}',
                status,
                assignee,
                priority,
                '{}',
                f'task-{task_key}',
            ),
        )


def test_idle_worker_task_heatmap_scores_idle_workers_by_queue_and_last_seen(tmp_path: Path) -> None:
    """接口应按空闲状态、最近接单时间和队列长度输出候选 worker。"""
    _init_test_db(tmp_path)
    create_task_queue_worker('backend-dev', '后端开发工程师', 'active', ['FastAPI', 'SQLite', 'backend'])
    create_task_queue_worker('qa-dev', '质量验证工程师', 'active', ['pytest', 'quality'])
    create_task_queue_worker('paused-dev', '暂停工程师', 'paused', ['backend'])
    _insert_task(tmp_path, 'ready-1', 'ready', None, 30)
    _insert_task(tmp_path, 'ready-2', 'todo', None, 10)
    _insert_task(tmp_path, 'busy-1', 'running', 'qa-dev', 20)

    with TestClient(app) as client:
        response = client.get(
            '/api/v1/workers/idle-task-heatmap',
            params={'workspace_path': str(tmp_path), 'limit': 5},
        )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已生成空闲 worker 任务热度图'
    assert body['data']['workspace_path'] == str(tmp_path.resolve())
    assert body['data']['summary']['dispatchable_queue_length'] == 2
    assert body['data']['summary']['worker_count'] == 3
    candidates = body['data']['candidates']
    assert [candidate['worker_key'] for candidate in candidates] == ['backend-dev', 'qa-dev', 'paused-dev']
    assert candidates[0]['idle'] is True
    assert candidates[0]['current_queue_length'] == 0
    assert candidates[1]['idle'] is False
    assert candidates[1]['current_queue_length'] == 1
    assert candidates[0]['score'] > candidates[1]['score'] > candidates[2]['score']
    assert candidates[0]['recommended_task'] == {
        'task_key': 'ready-1',
        'title': '中文任务 ready-1',
        'status': 'ready',
        'priority': 30,
    }
    assert candidates[0]['reasons']


def test_idle_worker_task_heatmap_rejects_invalid_limit(tmp_path: Path) -> None:
    """接口应对无效 limit 返回中文结构化错误。"""
    _init_test_db(tmp_path)
    with TestClient(app) as client:
        response = client.get(
            '/api/v1/workers/idle-task-heatmap',
            params={'workspace_path': str(tmp_path), 'limit': 0},
        )

    assert response.status_code == 422
    assert response.json() == {'detail': '输入校验失败'}
