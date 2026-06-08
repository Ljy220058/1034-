from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import create_task_queue_worker, upsert_workspace_task_item

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def _init_summary_db(tmp_path: Path) -> Path:
    """Initialize an isolated database for idle-task summary tests.

    Args:
        tmp_path: Temporary pytest directory.

    Returns:
        Path to the SQLite database.
    """
    db_path = tmp_path / 'idle-task-summary.db'
    database.init_db(db_path)
    return db_path


def _seed_workspace_tasks(workspace: str) -> None:
    """Seed workspace tasks for the summary endpoint.

    Args:
        workspace: Workspace path used for rows.
    """
    upsert_workspace_task_item(
        workspace_path=workspace,
        task_key='task-idle-1',
        title='空闲工作区任务',
        status='todo',
        description='用于摘要统计',
        assignee='backend-dev',
        priority=5,
        metadata={'summary': '用于摘要统计'},
    )
    upsert_workspace_task_item(
        workspace_path=workspace,
        task_key='task-running-1',
        title='运行中工作区任务',
        status='running',
        description='用于摘要统计',
        assignee='backend-dev',
        priority=6,
        metadata={'summary': '用于摘要统计'},
    )
    upsert_workspace_task_item(
        workspace_path=workspace,
        task_key='task-blocked-1',
        title='阻塞工作区任务',
        status='blocked',
        description='用于摘要统计',
        assignee='qa-tester',
        priority=7,
        metadata={'summary': '用于摘要统计', 'last_failure_reason': '数据库缺少默认值'},
    )


def _set_task_updated_at(workspace: str, task_key: str, updated_at: str) -> None:
    """Set a deterministic updated_at value for a workspace task.

    Args:
        workspace: Normalized workspace path.
        task_key: Workspace task key.
        updated_at: Timestamp text stored in SQLite.
    """
    with database.connect() as connection:
        connection.execute(
            'UPDATE workspace_tasks SET updated_at = ? WHERE workspace = ? AND task_key = ?',
            (updated_at, workspace, task_key),
        )


def test_idle_task_summary_endpoint_returns_chinese_api_payload(tmp_path: Path, monkeypatch) -> None:
    """Idle-task summary endpoint should return structured Chinese API payload."""
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(Path(__file__).resolve().parents[1]))
    db_path = _init_summary_db(tmp_path)
    database.init_db(db_path)
    workspace = str(tmp_path.resolve())
    _seed_workspace_tasks(workspace)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get('/api/v1/idle-task-summary/summary', params={'workspace_path': workspace})

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已返回空闲后端任务摘要'
    data = body['data']
    assert data['workspace_path'] == workspace
    assert data['summary']['pending_tasks'] == 3
    assert data['summary']['blocked_tasks'] == 1
    assert data['summary']['dispatch_recommendations'] == 0
    assert 'idle_card_prompts' in data['summary']
    assert data['recent_block_reasons'][0]['reason'] == '数据库缺少默认值'
    assert data['idle_workers'] == []


def test_idle_task_sidebar_endpoint_filters_tasks_and_rejects_invalid_status(tmp_path: Path) -> None:
    """Idle-task sidebar endpoint should filter tasks and validate status values."""
    db_path = _init_summary_db(tmp_path)
    database.init_db(db_path)
    workspace = str(tmp_path.resolve())
    _seed_workspace_tasks(workspace)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            '/api/v1/idle-task-summary/sidebar',
            params={'workspace_path': workspace, 'status': 'running'},
        )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已返回 running 任务侧栏'
    assert body['data']['status_filter'] == 'running'
    assert body['data']['summary']['total'] == 3
    assert body['data']['summary']['running'] == 1
    assert len(body['data']['tasks']) == 1
    assert body['data']['tasks'][0]['task_key'] == 'task-running-1'

    with TestClient(app, raise_server_exceptions=False) as client:
        invalid = client.get(
            '/api/v1/idle-task-summary/sidebar',
            params={'workspace_path': workspace, 'status': 'mystery'},
        )

    assert invalid.status_code == 422
    assert invalid.json() == {'detail': '状态筛选参数无效'}


def test_idle_card_auto_prompts_returns_chinese_reminders_for_stale_idle_worker_tasks(tmp_path: Path) -> None:
    """Auto prompt endpoint should only remind stale cards assigned to idle workers."""
    db_path = _init_summary_db(tmp_path)
    database.init_db(db_path)
    workspace = str(tmp_path.resolve())
    create_task_queue_worker('backend-dev', '后端开发工程师', 'active', ['FastAPI', 'SQLite'])
    create_task_queue_worker('qa-tester', '测试工程师', 'active', ['pytest'])
    upsert_workspace_task_item(
        workspace_path=workspace,
        task_key='stale-backend',
        title='中文创意：积压任务提醒',
        status='ready',
        description='等待后端空闲容量处理',
        assignee='backend-dev',
        priority=9,
        metadata={'summary': '等待后端空闲容量处理'},
    )
    upsert_workspace_task_item(
        workspace_path=workspace,
        task_key='fresh-backend',
        title='新近后端任务',
        status='ready',
        description='尚未达到提醒阈值',
        assignee='backend-dev',
        priority=8,
        metadata={'summary': '尚未达到提醒阈值'},
    )
    upsert_workspace_task_item(
        workspace_path=workspace,
        task_key='running-qa',
        title='运行中的测试任务',
        status='running',
        description='让 qa-tester 不再空闲',
        assignee='qa-tester',
        priority=7,
        metadata={'summary': '让 qa-tester 不再空闲'},
    )
    now = datetime.now(timezone.utc)
    _set_task_updated_at(workspace, 'stale-backend', (now - timedelta(hours=3)).isoformat())
    _set_task_updated_at(workspace, 'fresh-backend', now.isoformat())

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            '/api/v1/idle-task-summary/auto-prompts',
            params={'workspace_path': workspace, 'threshold_minutes': 60},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已生成空闲卡片自动提醒'
    data = payload['data']
    assert data['summary']['idle_workers'] == 1
    assert data['summary']['prompt_count'] == 1
    prompt = data['prompts'][0]
    assert prompt['task_key'] == 'stale-backend'
    assert prompt['assignee'] == 'backend-dev'
    assert prompt['suggested_priority'] in {'high', 'urgent'}
    assert '当前空闲' in prompt['reminder']
    assert '未被领取' in prompt['reminder']


def test_idle_card_auto_prompts_rejects_invalid_threshold(tmp_path: Path) -> None:
    """Auto prompt endpoint should return structured validation errors."""
    db_path = _init_summary_db(tmp_path)
    database.init_db(db_path)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            '/api/v1/idle-task-summary/auto-prompts',
            params={'workspace_path': str(tmp_path.resolve()), 'threshold_minutes': 0},
        )

    assert response.status_code == 422
    assert 'detail' in response.json()
