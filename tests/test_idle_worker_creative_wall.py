from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import create_task_queue_worker, reset_database, upsert_workspace_task_item


def _init_test_db(tmp_path: Path) -> None:
    """初始化任务看板测试数据库。"""
    database.init_db(tmp_path / 'running_club.db')


def _client(tmp_path: Path) -> TestClient:
    """创建带空闲 worker 创意墙路由的测试客户端。"""
    _init_test_db(tmp_path)
    create_task_queue_worker('backend-dev', '后端开发工程师', 'active', ['FastAPI', 'SQLite', 'backend'])
    create_task_queue_worker('reviewer-1', '代码审查员', 'paused', ['review', 'quality'])
    create_task_queue_worker('qa-1', '测试工程师', 'active', ['pytest', 'qa'])
    return TestClient(app)


def test_idle_worker_creative_wall_returns_api_response_shape(tmp_path: Path) -> None:
    """空闲 worker 创意墙接口应返回 ApiResponse 结构。"""
    client = _client(tmp_path)
    upsert_workspace_task_item(
        workspace_path=str(tmp_path),
        task_key='idea-1',
        title='后端创意任务',
        status='todo',
        description='为后端空闲 worker 提供创意卡片',
        assignee='none',
        priority=3,
        metadata={'idea': '创意墙卡片'},
    )

    response = client.get('/api/v1/workers/creative-wall', params={'workspace_path': str(tmp_path)})

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已生成空闲 worker 创意墙'
    assert payload['data']['workspace_path'] == str(tmp_path.resolve())
    assert 'summary' in payload['data']
    assert 'roles' in payload['data']
    assert isinstance(payload['data']['roles'], list)


def test_idle_worker_creative_wall_filters_worker_type(tmp_path: Path) -> None:
    """空闲 worker 创意墙接口应支持按 worker 类型筛选。"""
    client = _client(tmp_path)
    upsert_workspace_task_item(
        workspace_path=str(tmp_path),
        task_key='qa-idea-1',
        title='QA 创意任务',
        status='todo',
        description='为测试工程师提供创意卡片',
        assignee='none',
        priority=2,
        metadata={'idea': '测试创意'},
    )

    response = client.get(
        '/api/v1/workers/creative-wall',
        params={'workspace_path': str(tmp_path), 'worker_type': 'qa'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['data']['filters']['worker_type'] == 'qa'
    assert all(role['worker_type'] == 'qa' for role in payload['data']['roles'])


def test_idle_worker_creative_wall_excludes_busy_worker(tmp_path: Path) -> None:
    """已有 running 任务的 active worker 不应被识别为空闲。"""
    client = _client(tmp_path)
    upsert_workspace_task_item(
        workspace_path=str(tmp_path),
        task_key='busy-backend',
        title='后端执行中任务',
        status='running',
        description='backend worker 正在处理任务',
        assignee='backend-dev',
        priority=9,
        metadata={'idea': '执行中任务'},
    )

    response = client.get(
        '/api/v1/workers/creative-wall',
        params={'workspace_path': str(tmp_path), 'worker_type': 'backend'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['data']['summary']['idle_worker_count'] == 0
    assert payload['data']['roles'] == []


def test_idle_worker_creative_wall_returns_empty_roles_for_no_matching_type(tmp_path: Path) -> None:
    """没有匹配类型的空闲 worker 时应返回空结果而不是 500。"""
    client = _client(tmp_path)

    response = client.get(
        '/api/v1/workers/creative-wall',
        params={'workspace_path': str(tmp_path), 'worker_type': 'docs'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已生成空闲 worker 创意墙'
    assert payload['data']['filters']['worker_type'] == 'docs'
    assert payload['data']['summary']['idle_worker_count'] == 0
    assert payload['data']['summary']['idea_card_count'] == 0
    assert payload['data']['roles'] == []


def test_idle_worker_creative_wall_dispatch_returns_api_response_shape(tmp_path: Path) -> None:
    """一键分发接口应返回 ApiResponse 结构并绑定空闲 worker。"""
    client = _client(tmp_path)
    reset_database()
    database.init_db(tmp_path / 'running_club.db')
    create_task_queue_worker('backend-dev', '后端开发工程师', 'active', ['FastAPI', 'SQLite', 'backend'])
    create_task_queue_worker('qa-1', '测试工程师', 'active', ['pytest', 'qa'])
    upsert_workspace_task_item(
        workspace_path=str(tmp_path),
        task_key='backend-card',
        title='后端创意卡片',
        status='todo',
        description='可分发给后端 worker 的创意卡片',
        assignee='',
        priority=5,
        metadata={'idea': '后端创意卡片'},
    )

    response = client.post(
        '/api/v1/workers/creative-wall/dispatch',
        json={'workspace_path': str(tmp_path), 'worker_type': 'backend'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已分发空闲 worker 创意'
    assert payload['data']['workspace_path'] == str(tmp_path.resolve())
    assert payload['data']['worker']['worker_key'] == 'backend-dev'
    assert payload['data']['dispatch']['status'] == 'ready'


def test_idle_worker_creative_wall_dispatch_rejects_invalid_worker_type(tmp_path: Path) -> None:
    """非法 worker_type 应触发结构化校验错误。"""
    client = _client(tmp_path)

    response = client.post(
        '/api/v1/workers/creative-wall/dispatch',
        json={'workspace_path': str(tmp_path), 'worker_type': 'ops'},
    )

    assert response.status_code == 422
    assert response.json()['detail'] == 'worker_type 仅支持 backend、frontend、qa、docs、devops、security、review、idea'
