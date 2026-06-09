from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
import backend.routes.task_board as task_board
from backend.app import app


def _client(tmp_path: Path) -> TestClient:
    """Create a fresh test client backed by an isolated database."""
    database.init_db(tmp_path / 'task-board.db')
    return TestClient(app, raise_server_exceptions=False)


def test_task_board_intake_未登录验证访问返回200并返回规则卡片(tmp_path: Path) -> None:
    """任务看板入口是公开接口，未登录验证也应返回默认规则。"""
    client = _client(tmp_path)

    response = client.get('/api/v1/task-board/intake')

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已返回任务灵感看板默认规则'
    assert body['data']['count'] == 3


def test_task_board_route_缺少必填字段返回422(tmp_path: Path) -> None:
    """任务分流路径缺少必填字段时应返回 422。"""
    client = _client(tmp_path)

    response = client.post('/api/v1/task-board/route', json={'task_key': 'task-1'})

    assert response.status_code == 422
    body = response.json()
    assert body['detail'] == 'Field required'


def test_task_board_route_与_sidebar_兼容_dict_repo_return(tmp_path: Path, monkeypatch) -> None:
    """仓库辅助函数返回 dict 时，路由仍应正常工作。"""
    client = _client(tmp_path)

    monkeypatch.setattr(
        task_board,
        'build_worker_board',
        lambda workspace_path: {
            'idle_workers': [],
            'busy_workers': [
                {
                    'worker_key': 'worker-backend-1',
                    'name': 'Backend Worker',
                    'status': 'active',
                    'capabilities': ['fastapi', 'sqlite', 'backend'],
                }
            ],
        },
    )
    monkeypatch.setattr(
        task_board,
        'repository_list_workspace_task_items',
        lambda workspace_path, limit=20: [
            {
                'task_key': 'task-1',
                'title': '修复后端路由',
                'assignee': 'worker-backend-1',
                'status': 'running',
                'updated_at': '2026-06-09T00:00:00Z',
                'priority': 5,
                'workspace': str(workspace_path),
                'description': '处理 dict/model_dump 兼容性',
            }
        ],
    )

    route_response = client.post(
        '/api/v1/task-board/route',
        json={
            'task_key': 'task-2',
            'title': '修复活动分享卡片接口',
            'description': '兼容 PIL 服务端生成 PNG',
            'workspace_path': str(tmp_path),
            'limit': 10,
        },
    )
    sidebar_response = client.get('/api/v1/task-board/sidebar', params={'workspace_path': str(tmp_path), 'limit': 10})

    assert route_response.status_code == 200
    assert route_response.json()['data']['board_summary']['total_tasks'] == 1
    assert route_response.json()['data']['selected_worker']['worker_key'] == 'worker-backend-1'
    assert sidebar_response.status_code == 200
    assert sidebar_response.json()['data']['summary']['running'] == 1
