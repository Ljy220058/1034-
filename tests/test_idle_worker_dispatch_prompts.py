from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import upsert_workspace_task_item
from backend.worker_recommendations import upsert_queue_worker

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def _client(tmp_path: Path) -> TestClient:
    """创建绑定临时数据库的测试客户端。

    Args:
        tmp_path: pytest 临时目录。

    Returns:
        FastAPI TestClient 实例。
    """
    database.init_db(tmp_path / 'idle-dispatch-prompts.db')
    return TestClient(app, raise_server_exceptions=False)


def test_idle_dispatch_prompts_return_chinese_structured_advice(tmp_path: Path) -> None:
    """空闲 worker 智能派发提示应返回中文结构化建议。"""
    client = _client(tmp_path)
    upsert_queue_worker('backend-dev', '后端开发', 'active', ['FastAPI', 'SQLite', 'API'])
    upsert_queue_worker('quality-gate', '质量门禁', 'active', ['pytest', 'review', '验收'])
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='running-backend',
        title='实现后端接口',
        status='running',
        description='正在实现 FastAPI 接口',
        assignee='backend-dev',
        priority=9,
    )
    upsert_workspace_task_item(
        workspace_path=WORKSPACE_ROOT,
        task_key='ready-review',
        title='抽查接口测试覆盖',
        status='ready',
        description='需要 pytest 和质量验收',
        assignee=None,
        priority=8,
    )

    response = client.get('/api/v1/workers/idle-dispatch-prompts', params={'workspace_path': str(WORKSPACE_ROOT)})

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已生成空闲 worker 智能派发提示'
    data = body['data']
    assert set(data.keys()) == {'workspace_path', 'summary', 'next_step_advice', 'idle_workers', 'dispatch_prompts'}
    assert data['summary']['idle_worker_count'] == 1
    assert data['summary']['ready_task_count'] == 1
    assert '建议优先派发' in data['next_step_advice']
    prompt = data['dispatch_prompts'][0]
    assert prompt['worker_key'] == 'quality-gate'
    assert prompt['recommended_task_type'] == '测试验收类任务'
    assert '中文提示' in prompt
    assert '适合接收新任务' in prompt['中文提示']


def test_idle_dispatch_prompts_empty_board_has_chinese_hint(tmp_path: Path) -> None:
    """空数据时应返回中文空状态提示且保持 ApiResponse 结构。"""
    client = _client(tmp_path)

    response = client.get('/api/v1/workers/idle-dispatch-prompts', params={'workspace_path': str(WORKSPACE_ROOT)})

    assert response.status_code == 200
    body = response.json()
    assert body == {
        'data': {
            'workspace_path': str(WORKSPACE_ROOT),
            'summary': {
                'idle_worker_count': 0,
                'busy_worker_count': 0,
                'ready_task_count': 0,
                'running_task_count': 0,
                'blocked_task_count': 0,
            },
            'next_step_advice': '当前没有空闲 worker 或待派发任务，请先补充 worker intake 或新任务。',
            'idle_workers': [],
            'dispatch_prompts': [],
        },
        'message': '已生成空闲 worker 智能派发提示',
    }


def test_idle_dispatch_prompts_rejects_invalid_workspace() -> None:
    """非法工作区参数应返回中文结构化错误。"""
    response = TestClient(app, raise_server_exceptions=False).get(
        '/api/v1/workers/idle-dispatch-prompts',
        params={'workspace_path': 'relative/path'},
    )

    assert response.status_code == 422
    assert response.json() == {'detail': '工作区参数不合法'}
