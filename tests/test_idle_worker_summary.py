from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import create_task_queue_worker


def _init_test_db(tmp_path: Path) -> None:
    """初始化任务看板测试数据库。"""
    database.init_db(tmp_path / 'running_club.db')


def _client(tmp_path: Path) -> TestClient:
    """创建带空闲 worker 摘要路由的测试客户端。"""
    _init_test_db(tmp_path)
    create_task_queue_worker('backend-dev', '后端开发工程师', 'active', ['FastAPI', 'SQLite', 'backend'])
    create_task_queue_worker('reviewer-1', '代码审查员', 'paused', ['review', 'quality'])
    create_task_queue_worker('qa-1', '测试工程师', 'active', ['pytest', 'qa'])
    return TestClient(app)


def test_idle_worker_summary_returns_api_response_shape(tmp_path: Path) -> None:
    """空闲 worker 摘要接口应返回 ApiResponse 结构。"""
    client = _client(tmp_path)

    response = client.get('/api/v1/workers/idle-summary', params={'workspace_path': str(tmp_path)})

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已生成空闲 worker 摘要'
    assert payload['data']['workspace_path'] == str(tmp_path.resolve())
    assert isinstance(payload['data']['idle_workers'], list)
    assert isinstance(payload['data']['pending_tasks'], list)
    assert isinstance(payload['data']['recommendations'], list)
    assert len(payload['data']['recommendations']) == 2


def test_idle_worker_recommendations_returns_api_response_shape(tmp_path: Path) -> None:
    """空闲 worker 推荐接口应返回 ApiResponse 结构。"""
    client = _client(tmp_path)

    response = client.get('/api/v1/workers/idle-recommendations', params={'workspace_path': str(tmp_path)})

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已生成空闲 worker 可执行推荐'
    assert payload['data']['workspace_path'] == str(tmp_path.resolve())
    assert 'snapshot' in payload['data']
    assert 'summary' in payload['data']
    assert 'tasks' in payload['data']


def test_idle_worker_summary_rejects_empty_workspace_path() -> None:
    """空 workspace_path 应触发结构化错误。"""
    response = TestClient(app).get('/api/v1/workers/idle-summary', params={'workspace_path': ' '})

    assert response.status_code == 422
    assert response.json() == {'detail': 'workspace_path 不能为空'}
