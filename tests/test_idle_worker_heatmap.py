from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import create_task_queue_worker


def _init_test_db(tmp_path: Path) -> None:
    """初始化任务看板测试数据库。

    Args:
        tmp_path: pytest 临时目录。
    """
    database.init_db(tmp_path / 'running_club.db')


def test_worker_heatmap_returns_ranked_candidates(tmp_path: Path) -> None:
    """热度图接口应返回排序后的候选列表。"""
    _init_test_db(tmp_path)
    create_task_queue_worker('backend-dev', '后端开发工程师', 'active', ['FastAPI', 'SQLite', 'backend'])
    create_task_queue_worker('reviewer-1', '代码审查员', 'active', ['review', 'quality'])
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO workspace_tasks (workspace, task_key, title, status, assignee, priority, metadata, task_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(tmp_path.resolve()),
                'blocked-task',
                '中文阻塞任务',
                'blocked',
                'backend-dev',
                10,
                '{"last_failure_reason": "数据库锁超时"}',
                'task-001',
            ),
        )
        connection.execute(
            """
            INSERT INTO workspace_tasks (workspace, task_key, title, status, assignee, priority, metadata, task_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(tmp_path.resolve()),
                'ready-task',
                '中文待办任务',
                'ready',
                'reviewer-1',
                5,
                '{}',
                'task-002',
            ),
        )

    with TestClient(app) as client:
        response = client.get(
            '/api/v1/workers/heatmap',
            params={'workspace_path': str(tmp_path), 'limit': 5},
        )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已生成任务热度图'
    assert body['data']['workspace_path'] == str(tmp_path.resolve())
    assert body['data']['summary']['total_candidates'] == 2
    assert isinstance(body['data']['candidates'], list)
    assert body['data']['candidates'][0]['score'] >= body['data']['candidates'][1]['score']
    assert body['data']['candidates'][0]['reasons']


def test_worker_heatmap_rejects_invalid_limit(tmp_path: Path) -> None:
    """热度图接口应对无效参数返回结构化错误。"""
    _init_test_db(tmp_path)
    with TestClient(app) as client:
        response = client.get(
            '/api/v1/workers/heatmap',
            params={'workspace_path': str(tmp_path), 'limit': 0},
        )

    assert response.status_code == 422
    assert response.json() == {'detail': '输入校验失败'}
