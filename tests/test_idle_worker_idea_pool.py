from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import upsert_workspace_task_item
from backend.worker_recommendations import upsert_queue_worker
from conftest import make_auth_headers

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def _client(tmp_path: Path) -> TestClient:
    """创建绑定临时数据库的测试客户端。

    Args:
        tmp_path: pytest 临时目录。

    Returns:
        FastAPI TestClient 实例。
    """
    db_path = tmp_path / 'idle-worker-idea-pool.db'
    if db_path.exists():
        db_path.unlink()
    database.init_db(db_path)
    return TestClient(app, raise_server_exceptions=False)


def test_idle_worker_idea_pool_groups_candidates_by_worker_role(tmp_path: Path) -> None:
    """空闲 worker 创意池应按角色返回可承接候选卡片。"""
    client = _client(tmp_path)
    upsert_queue_worker('backend-dev', '后端开发', 'active', ['FastAPI', 'SQLite', 'API'])
    upsert_queue_worker('frontend-dev', '前端开发', 'active', ['HTML', 'CSS', '页面'])
    upsert_queue_worker('quality-gate', '质量门禁', 'paused', ['pytest', 'review'])
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='backend-api-card',
        title='创意：后端 API 摘要卡片',
        status='ready',
        description='实现 FastAPI SQLite 汇总接口',
        assignee=None,
        priority=9,
    )
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='frontend-page-card',
        title='创意：前端展示页面',
        status='todo',
        description='实现 HTML CSS 可视化页面',
        assignee=None,
        priority=5,
    )
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='running-backend',
        title='正在处理的后端任务',
        status='running',
        description='backend-dev 正在处理',
        assignee='backend-dev',
        priority=10,
    )

    response = client.get(
        '/api/v1/workers/idle-idea-pool',
        params={'workspace_path': str(WORKSPACE_ROOT), 'status': 'ready'},
        headers=make_auth_headers(client, '19900001001', 'admin'),
    )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已生成空闲 worker 创意池'
    data = body['data']
    assert data['summary'] == {
        'idle_worker_count': 1,
        'candidate_count': 1,
        'role_count': 1,
    }
    assert data['roles'][0]['role'] == 'frontend'
    assert data['roles'][0]['workers'][0]['worker_key'] == 'frontend-dev'
    assert data['roles'][0]['candidates'][0]['task_key'] == 'backend-api-card'
    assert data['roles'][0]['candidates'][0]['status'] == 'ready'
    assert '推荐给 frontend-dev' in data['roles'][0]['candidates'][0]['reason']


def test_idle_worker_idea_pool_supports_role_and_status_filters(tmp_path: Path) -> None:
    """创意池应支持按 worker 角色和任务状态筛选。"""
    client = _client(tmp_path)
    upsert_queue_worker('backend-dev', '后端开发', 'active', ['FastAPI', 'SQLite'])
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='todo-backend-card',
        title='创意：后端数据接口',
        status='todo',
        description='补充 SQLite 只读接口',
        assignee=None,
        priority=7,
    )
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='ready-review-card',
        title='创意：质量验收巡检',
        status='ready',
        description='补充 pytest 验证',
        assignee=None,
        priority=8,
    )

    response = client.get(
        '/api/v1/workers/idle-idea-pool',
        params={'workspace_path': str(WORKSPACE_ROOT), 'role': 'backend', 'status': 'todo'},
        headers=make_auth_headers(client, '19900001002', 'leader'),
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['summary']['idle_worker_count'] == 1
    assert data['summary']['candidate_count'] == 1
    assert data['roles'][0]['role'] == 'backend'
    assert [item['task_key'] for item in data['roles'][0]['candidates']] == ['todo-backend-card']


def test_idle_worker_idea_pool_requires_admin_or_leader(tmp_path: Path) -> None:
    """普通成员访问创意池应返回中文结构化权限错误。"""
    client = _client(tmp_path)

    response = client.get(
        '/api/v1/workers/idle-idea-pool',
        params={'workspace_path': str(WORKSPACE_ROOT)},
        headers=make_auth_headers(client, '19900001003', 'member'),
    )

    assert response.status_code == 403
    assert response.json() == {'detail': '仅管理员或团长可查看'}


def test_idle_worker_idea_pool_rejects_bad_filters(tmp_path: Path) -> None:
    """非法筛选条件应返回中文结构化错误。"""
    client = _client(tmp_path)

    response = client.get(
        '/api/v1/workers/idle-idea-pool',
        params={'workspace_path': str(WORKSPACE_ROOT), 'role': 'unknown'},
        headers=make_auth_headers(client, '19900001004', 'admin'),
    )

    assert response.status_code == 422
    assert response.json() == {'detail': 'worker 角色不合法'}
