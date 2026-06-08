from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import create_task_queue_worker, upsert_workspace_task_item


def _init_test_db(tmp_path: Path) -> None:
    """初始化任务看板测试数据库。"""
    database.init_db(tmp_path / 'running_club.db')


def test_worker_dashboard_summary_exposes_idle_workers_and_reasons(tmp_path: Path) -> None:
    """空闲 worker 总览接口应返回可用于调度的摘要。"""
    _init_test_db(tmp_path)
    create_task_queue_worker('backend-dev', '后端开发工程师', 'active', ['FastAPI', 'SQLite', 'backend'])
    create_task_queue_worker('reviewer-1', '代码审查员', 'active', ['review', 'quality'])
    create_task_queue_worker('frontend-dev', '前端开发工程师', 'paused', ['HTML', 'CSS', 'frontend'])
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
                'todo-task',
                '中文待办任务',
                'todo',
                'reviewer-1',
                5,
                '{}',
                'task-002',
            ),
        )

    with TestClient(app) as client:
        response = client.get(
            '/api/v1/dashboard/digest/summary',
            params={'workspace_path': str(tmp_path)},
        )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已返回空闲度概览面板'
    assert body['data']['workspace_path'] == str(tmp_path.resolve())
    assert body['data']['summary']['idle_count'] >= 1
    assert body['data']['summary']['blocked'] >= 1
    assert isinstance(body['data']['workers'], list)
    assert isinstance(body['data']['highlighted_workers'], list)
    assert isinstance(body['data']['board']['recent_tasks'], list)
    assert body['data']['board']['recent_tasks']


def test_worker_dashboard_sidebar_filters_status_and_validates_input(tmp_path: Path) -> None:
    """侧栏接口应支持状态筛选并返回结构化错误。"""
    _init_test_db(tmp_path)
    create_task_queue_worker('backend-dev', '后端开发工程师', 'active', ['FastAPI', 'SQLite', 'backend'])
    create_task_queue_worker('reviewer-1', '测试工程师', 'paused', ['pytest', 'qa'])
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
            '/api/v1/workers/digest',
            params={'workspace_path': str(tmp_path), 'status': 'blocked'},
        )
        invalid = client.get(
            '/api/v1/workers/digest',
            params={'workspace_path': str(tmp_path), 'status': 'invalid'},
        )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已返回 blocked 任务侧栏'
    assert body['data']['status_filter'] == 'blocked'
    assert all(task['status'] == 'blocked' for task in body['data']['tasks'])
    assert invalid.status_code == 422
    assert invalid.json() == {'detail': '状态筛选参数无效'}
