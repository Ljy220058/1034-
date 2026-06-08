from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import create_task_queue_worker, upsert_workspace_task_item


def _client(tmp_path: Path) -> TestClient:
    """创建使用隔离数据库的测试客户端。"""
    database.init_db(tmp_path / 'creative-wall.db')
    return TestClient(app, raise_server_exceptions=False)


def test_idle_worker_creative_wall_groups_idle_workers_by_role(tmp_path: Path) -> None:
    """创意墙接口应按 worker 角色汇总空闲 worker 与可接手创意卡片。"""
    client = _client(tmp_path)
    workspace_path = str(tmp_path)
    create_task_queue_worker('backend-dev', '后端开发工程师', 'active', ['FastAPI', 'SQLite', 'backend'])
    create_task_queue_worker('frontend-dev', '前端开发工程师', 'active', ['UI', 'CSS'])
    create_task_queue_worker('qa-dev', '测试工程师', 'paused', ['pytest'])
    upsert_workspace_task_item(
        workspace_path=workspace_path,
        task_key='backend-card',
        title='实现空闲 worker 创意墙接口',
        status='ready',
        description='后端负责 FastAPI 与 SQLite 聚合',
        assignee='backend-dev',
        priority=9,
        metadata={'idea': '按角色展示可接手功能创意'},
    )
    upsert_workspace_task_item(
        workspace_path=workspace_path,
        task_key='frontend-card',
        title='实现创意墙最小页面',
        status='todo',
        description='前端负责页面渲染',
        assignee='frontend-dev',
        priority=5,
        metadata={'idea': '最小创意墙页面'},
    )
    upsert_workspace_task_item(
        workspace_path=workspace_path,
        task_key='running-card',
        title='正在执行任务不应推荐',
        status='running',
        description='已有执行中任务',
        assignee='backend-dev',
        priority=1,
        metadata={},
    )

    response = client.get('/api/v1/workers/creative-wall', params={'workspace_path': workspace_path})

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已生成空闲 worker 创意墙'
    data = body['data']
    assert data['summary']['idle_worker_count'] == 2
    assert data['summary']['role_count'] == 2
    assert data['summary']['idea_card_count'] == 2
    role_names = [role['role'] for role in data['roles']]
    assert role_names == ['后端开发', '前端开发']
    backend_role = data['roles'][0]
    assert backend_role['worker_type'] == 'backend'
    assert backend_role['idle_workers'][0]['worker_key'] == 'backend-dev'
    assert backend_role['idea_cards'][0]['task_key'] == 'backend-card'
    assert backend_role['idea_cards'][0]['status'] == 'ready'
    assert backend_role['idea_cards'][0]['cta'] == '交给后端开发处理'
    assert '正在执行任务不应推荐' not in str(data)


def test_idle_worker_creative_wall_filters_by_worker_type(tmp_path: Path) -> None:
    """创意墙接口应支持按 worker 类型筛选。"""
    client = _client(tmp_path)
    workspace_path = str(tmp_path)
    create_task_queue_worker('backend-dev', '后端开发工程师', 'active', ['backend'])
    create_task_queue_worker('docs-writer', '文档撰写员', 'active', ['docs'])
    upsert_workspace_task_item(
        workspace_path=workspace_path,
        task_key='backend-card',
        title='后端接口创意',
        status='ready',
        description='FastAPI 接口',
        assignee='backend-dev',
        priority=9,
        metadata={},
    )
    upsert_workspace_task_item(
        workspace_path=workspace_path,
        task_key='docs-card',
        title='文档创意',
        status='ready',
        description='补充用户指南',
        assignee='docs-writer',
        priority=6,
        metadata={},
    )

    response = client.get(
        '/api/v1/workers/creative-wall',
        params={'workspace_path': workspace_path, 'worker_type': 'docs'},
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['summary']['idle_worker_count'] == 1
    assert data['filters']['worker_type'] == 'docs'
    assert [role['worker_type'] for role in data['roles']] == ['docs']
    assert data['roles'][0]['idea_cards'][0]['task_key'] == 'docs-card'


def test_idle_worker_creative_wall_rejects_unknown_worker_type(tmp_path: Path) -> None:
    """未知 worker 类型应返回中文结构化错误。"""
    client = _client(tmp_path)

    response = client.get(
        '/api/v1/workers/creative-wall',
        params={'workspace_path': str(tmp_path), 'worker_type': 'unknown'},
    )

    assert response.status_code == 422
    assert response.json() == {'detail': 'worker_type 仅支持 backend、frontend、qa、docs、devops、security、review、idea'}


def test_dispatch_idle_worker_creative_wall_assigns_top_card(tmp_path: Path) -> None:
    """一键分发接口应把最高优先级创意卡片分配给匹配的空闲 worker。"""
    client = _client(tmp_path)
    workspace_path = str(tmp_path)
    create_task_queue_worker('backend-dev', '后端开发工程师', 'active', ['backend', 'FastAPI'])
    upsert_workspace_task_item(
        workspace_path=workspace_path,
        task_key='low-card',
        title='后端低优先级创意',
        status='todo',
        description='FastAPI 接口优化',
        assignee=None,
        priority=1,
        metadata={'idea': '低优先级候选'},
    )
    upsert_workspace_task_item(
        workspace_path=workspace_path,
        task_key='top-card',
        title='后端高优先级创意',
        status='ready',
        description='SQLite 聚合接口',
        assignee=None,
        priority=9,
        metadata={'idea': '高优先级候选'},
    )

    response = client.post(
        '/api/v1/workers/creative-wall/dispatch',
        json={'workspace_path': workspace_path, 'worker_type': 'backend'},
    )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已分发空闲 worker 创意'
    data = body['data']
    assert data['worker']['worker_key'] == 'backend-dev'
    assert data['idea_card']['task_key'] == 'top-card'
    assert data['idea_card']['status'] == 'ready'
    assert data['dispatch']['assignee'] == 'backend-dev'
    assert data['dispatch']['task_key'] == 'top-card'


def test_dispatch_idle_worker_creative_wall_can_target_task_key(tmp_path: Path) -> None:
    """一键分发接口应支持指定创意卡片键。"""
    client = _client(tmp_path)
    workspace_path = str(tmp_path)
    create_task_queue_worker('docs-writer', '文档撰写员', 'active', ['docs'])
    upsert_workspace_task_item(
        workspace_path=workspace_path,
        task_key='docs-card',
        title='文档创意',
        status='todo',
        description='补充用户指南',
        assignee=None,
        priority=3,
        metadata={'idea': '补文档'},
    )

    response = client.post(
        '/api/v1/workers/creative-wall/dispatch',
        json={'workspace_path': workspace_path, 'worker_type': 'docs', 'task_key': 'docs-card'},
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['idea_card']['task_key'] == 'docs-card'
    assert data['dispatch']['assignee'] == 'docs-writer'


def test_dispatch_idle_worker_creative_wall_returns_404_when_no_card(tmp_path: Path) -> None:
    """没有可分发创意时应返回中文结构化错误。"""
    client = _client(tmp_path)
    create_task_queue_worker('qa-dev', '测试工程师', 'active', ['qa'])

    response = client.post(
        '/api/v1/workers/creative-wall/dispatch',
        json={'workspace_path': str(tmp_path), 'worker_type': 'qa'},
    )

    assert response.status_code == 404
    assert response.json() == {'detail': '没有可分发的创意卡片'}
