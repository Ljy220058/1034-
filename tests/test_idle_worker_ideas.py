from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import create_task_queue_worker, upsert_workspace_task_item


def _client(tmp_path: Path) -> TestClient:
    """创建使用隔离数据库的测试客户端。

    Args:
        tmp_path: pytest 临时目录。

    Returns:
        FastAPI TestClient 实例。
    """
    database.init_db(tmp_path / 'idle-worker-ideas.db')
    return TestClient(app, raise_server_exceptions=False)


def test_idle_worker_ideas_returns_two_actionable_chinese_suggestions(tmp_path: Path) -> None:
    """接口应基于空闲 worker 和负载生成两条可创建任务建议。"""
    client = _client(tmp_path)
    workspace_path = str(tmp_path)
    create_task_queue_worker('backend-dev', '后端开发工程师', 'active', ['FastAPI', 'SQLite', 'backend'])
    create_task_queue_worker('docs-writer', '文档撰写员', 'active', ['docs', 'README'])
    create_task_queue_worker('frontend-dev', '前端开发工程师', 'paused', ['UI'])
    upsert_workspace_task_item(
        workspace_path=workspace_path,
        task_key='backend-running',
        title='正在实现后端统计接口',
        status='running',
        description='后端当前已有执行中任务',
        assignee='backend-dev',
        priority=9,
        metadata={},
    )
    upsert_workspace_task_item(
        workspace_path=workspace_path,
        task_key='docs-ready',
        title='补充跑团管理使用指南',
        status='ready',
        description='文档负责人当前空闲，可补充中文用户指南',
        assignee=None,
        priority=7,
        metadata={},
    )

    response = client.get('/api/v1/workers/idle-ideas', params={'workspace_path': workspace_path})

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已生成空闲 worker 功能创意建议'
    data = body['data']
    assert data['summary'] == {
        'idle_worker_count': 2,
        'running_task_count': 1,
        'suggestion_count': 2,
    }
    assert len(data['suggestions']) == 2
    first = data['suggestions'][0]
    assert set(first) == {'type', 'title', 'description', 'recommended_assignee', 'source'}
    assert first['recommended_assignee'] == 'docs-writer'
    assert first['title'].startswith('中文功能：')
    assert '可直接创建为任务' in first['description']
    assert data['suggestions'][1]['recommended_assignee'] == 'backend-dev'


def test_idle_worker_ideas_supports_worker_type_filter(tmp_path: Path) -> None:
    """接口应支持按 worker 类型筛选推荐负责人。"""
    client = _client(tmp_path)
    workspace_path = str(tmp_path)
    create_task_queue_worker('backend-dev', '后端开发工程师', 'active', ['backend'])
    create_task_queue_worker('qa-dev', '测试工程师', 'active', ['pytest', 'qa'])

    response = client.get(
        '/api/v1/workers/idle-ideas',
        params={'workspace_path': workspace_path, 'worker_type': 'qa'},
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['filters']['worker_type'] == 'qa'
    assert [item['recommended_assignee'] for item in data['suggestions']] == ['qa-dev', 'qa-dev']
    assert all(item['type'] == 'qa' for item in data['suggestions'])


def test_idle_worker_ideas_rejects_unknown_worker_type(tmp_path: Path) -> None:
    """未知 worker 类型应返回中文结构化错误。"""
    client = _client(tmp_path)

    response = client.get(
        '/api/v1/workers/idle-ideas',
        params={'workspace_path': str(tmp_path), 'worker_type': 'unknown'},
    )

    assert response.status_code == 422
    assert response.json() == {'detail': 'worker_type 仅支持 backend、frontend、qa、docs、devops、security、review、idea'}
