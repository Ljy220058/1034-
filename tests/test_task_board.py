from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app


def _client(tmp_path: Path) -> TestClient:
    """Create a fresh test client backed by an isolated database."""
    database.init_db(tmp_path / 'task-board.db')
    return TestClient(app, raise_server_exceptions=False)


def test_task_board_intake_未认证访问返回200并返回规则卡片(tmp_path: Path) -> None:
    """任务看板入口是公开接口，未认证也应返回默认规则。"""
    client = _client(tmp_path)

    response = client.get('/api/v1/task-board/intake')

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已返回任务灵感看板默认规则'
    assert body['data']['count'] == 3


def test_task_board_route_缺少必填字段返回422(tmp_path: Path) -> None:
    """任务分流路由缺少必填字段时应返回 422。"""
    client = _client(tmp_path)

    response = client.post('/api/v1/task-board/route', json={'task_key': 'task-1'})

    assert response.status_code == 422
