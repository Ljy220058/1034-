from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from conftest import make_auth_headers
from backend.repository import create_task_queue_worker, upsert_workspace_task_item


def _init_test_db(tmp_path: Path) -> None:
    """初始化任务看板测试数据库。

    Args:
        tmp_path: pytest 临时目录。
    """
    database.init_db(tmp_path / 'running_club.db')


def test_task_board_suggest_prefers_backend_for_chinese_title(tmp_path: Path, monkeypatch) -> None:
    """Task board suggestion should infer backend work from Chinese task text."""
    _init_test_db(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            '/api/v1/task-board/suggest',
            headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
            json={
                'title': '中文功能创意：智能任务看板自动分流',
                'description': '实现一个根据任务标题与描述自动推荐分配到后端、前端、测试或评审 worker 的看板分流功能。',
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已生成任务分流建议'
    assert body['data']['recommended_role'] == 'backend'
    assert body['data']['recommended_worker'] is None
    assert '推荐分流到 backend worker' in body['data']['reason']



def test_task_board_suggest_falls_back_to_review_when_unknown(tmp_path: Path, monkeypatch) -> None:
    """Task board suggestion should fall back to review when no signals match."""
    _init_test_db(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            '/api/v1/task-board/suggest',
            headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
            json={
                'title': '为看板补充新功能',
                'description': '一个不明确的任务。',
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body['data']['recommended_role'] == 'backend'
    assert '默认倾向后端实现复杂逻辑' in body['data']['reason']



def test_task_board_suggest_prefers_idle_matching_worker(tmp_path: Path) -> None:
    """任务分流建议应优先选择空闲且能力匹配的 worker。"""
    _init_test_db(tmp_path)
    create_task_queue_worker('backend-dev', '后端开发工程师', 'active', ['FastAPI', 'SQLite', 'backend'])
    create_task_queue_worker('frontend-dev', '前端开发工程师', 'paused', ['HTML', 'CSS', 'frontend'])

    with TestClient(app) as client:
        response = client.post(
            '/api/v1/task-board/suggest',
            headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
            json={
                'title': '新增成员注册 API',
                'description': '使用 FastAPI 和 SQLite 实现后端接口，并返回结构化错误。',
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body['data']['recommended_role'] == 'backend'
    assert body['data']['recommended_worker'] == 'backend-dev'
    assert '优先选择 backend-dev' in body['data']['reason']
    assert body['data']['candidates'][0]['worker_key'] == 'backend-dev'


BLOCKED_TASK_EXAMPLE = {
    'task_id': 't_blocked',
    'title': '后端任务卡住：数据库迁移失败',
    'status': 'blocked',
    'assignee': 'backend-dev',
    'workspace': '/workspace/project',
    'block_reason': '迁移脚本缺少字段默认值，需要确认是否允许填 0。',
    'comments': [
        {'body': '执行 pytest tests/test_api.py 失败，sqlite 提示 NOT NULL constraint failed。'},
    ],
    'recent_events': [
        {'kind': 'blocked', 'payload': {'reason': '迁移脚本缺少字段默认值'}, 'created_at': '2026-06-06T10:00:00+00:00'},
    ],
}

TRIAGE_TASK_EXAMPLE = {
    'task_id': 't_triage',
    'title': '前端任务多次失败后进入 triage',
    'status': 'triage',
    'assignee': 'frontend-dev',
    'workspace': '/workspace/project',
    'comments': [{'body': '连续三次启动失败，最后一次是依赖安装超时。'}],
    'recent_events': [{'kind': 'spawn_failed', 'payload': {'error': 'dependency install timed out'}}],
}

TODO_TASK_EXAMPLE = {
    'task_id': 't_todo',
    'title': '补充文档说明',
    'status': 'todo',
    'assignee': 'writer',
    'workspace': '/workspace/project',
    'comments': [],
    'recent_events': [{'kind': 'created', 'payload': {'assignee': 'writer'}}],
}



def test_blocked_task_unblock_advice_uses_reusable_reason_fields() -> None:
    from backend.blocked_task_advice import build_blocked_task_advice

    advice = build_blocked_task_advice(BLOCKED_TASK_EXAMPLE)

    assert advice['language'] == 'zh-CN'
    assert advice['task_id'] == 't_blocked'
    assert advice['status'] == 'blocked'
    assert '迁移脚本缺少字段默认值' in advice['sections']['可能原因']
    assert 'backend-dev' in advice['sections']['建议动作']
    assert '/workspace/project' in advice['sections']['建议动作']
    assert '是否允许填 0' in advice['sections']['需要人工确认的信息']



def test_triage_task_advice_recommends_archive_recreate_and_uses_recent_events() -> None:
    from backend.blocked_task_advice import build_blocked_task_advice

    advice = build_blocked_task_advice(TRIAGE_TASK_EXAMPLE)

    assert advice['status'] == 'triage'
    assert '连续失败或系统自动分拣' in advice['sections']['可能原因']
    assert 'archive + recreate' in advice['sections']['建议动作']
    assert 'dependency install timed out' in advice['evidence']['recent_events'][0]



def test_todo_task_advice_is_non_blocking_example_data() -> None:
    from backend.blocked_task_advice import build_blocked_task_advice

    advice = build_blocked_task_advice(TODO_TASK_EXAMPLE)

    assert advice['status'] == 'todo'
    assert '当前未处于 blocked/triage' in advice['sections']['可能原因']
    assert '保持队列流转' in advice['sections']['建议动作']
    assert advice['sections']['需要人工确认的信息'] == '暂无必须人工确认的信息；如验收标准不清，再补充评论说明。'



def test_blocked_task_advice_endpoint_returns_chinese_three_sections() -> None:
    with TestClient(app) as client:
        response = client.post(
            '/api/v1/task-board/unblock-advice',
            headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
            json=BLOCKED_TASK_EXAMPLE,
        )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已生成阻塞任务自助解锁建议'
    assert set(body['data']['sections']) == {'可能原因', '建议动作', '需要人工确认的信息'}
    assert all(isinstance(value, str) and value for value in body['data']['sections'].values())



def test_task_board_workers_endpoint_returns_workers_and_summary() -> None:
    """Task board workers endpoint should return ApiResponse shape."""
    create_task_queue_worker('backend-dev', '后端开发工程师', 'active', ['FastAPI', 'SQLite', 'backend'])
    create_task_queue_worker('qa-dev', '测试工程师', 'paused', ['pytest', 'qa'])

    with TestClient(app) as client:
        response = client.get(
            '/api/v1/task-board/workers',
            headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
        )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已返回 worker 列表'
    assert 'workers' in body['data']
    assert body['data']['summary']['total'] >= 1
    assert any(worker['status'] == 'active' for worker in body['data']['workers'])



def test_task_board_sidebar_endpoint_returns_filtered_tasks_and_summary(tmp_path: Path) -> None:
    """任务可视化侧栏应返回筛选后的任务与统计信息。"""
    _init_test_db(tmp_path)
    workspace = str(tmp_path.resolve())
    upsert_workspace_task_item(
        workspace_path=workspace,
        task_key='task-001',
        title='中文任务：实现侧栏筛选',
        status='running',
        description='为任务看板增加任务可视化侧栏与状态筛选。',
        assignee='backend-dev',
        priority=7,
        metadata={'description': '为任务看板增加任务可视化侧栏与状态筛选。'},
        task_id='t_sidebar_001',
    )
    upsert_workspace_task_item(
        workspace_path=workspace,
        task_key='task-002',
        title='中文任务：补充测试',
        status='todo',
        description='补充侧栏接口的测试覆盖。',
        assignee='qa-dev',
        priority=3,
        metadata={'description': '补充侧栏接口的测试覆盖。'},
        task_id='t_sidebar_002',
    )

    with TestClient(app) as client:
        response = client.get(
            '/api/v1/task-board/sidebar',
            params={'workspace_path': workspace, 'status': 'running'},
            headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
        )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已返回 running 任务侧栏'
    assert body['data']['status_filter'] == 'running'
    assert body['data']['summary']['total'] == 2
    assert body['data']['summary']['running'] == 1
    assert len(body['data']['tasks']) == 1
    assert body['data']['tasks'][0]['task_key'] == 'task-001'
    assert body['data']['tasks'][0]['workspace'] == workspace


def test_workspace_task_batch_create_requires_authentication(tmp_path: Path) -> None:
    """未登录访问批量创建接口应返回 401。"""
    _init_test_db(tmp_path)
    workspace = str(tmp_path.resolve())

    with TestClient(app) as client:
        response = client.post(
            '/api/v1/workspaces/tasks/items/batch',
            json={
                'workspace_path': workspace,
                'items': [
                    {
                        'task_key': 'task-batch-001',
                        'title': '中文任务：批量创建测试',
                        'description': '验证批量创建接口的认证与权限。',
                        'status': 'todo',
                        'assignee': 'backend-dev',
                        'priority': 1,
                    }
                ],
            },
        )

    assert response.status_code == 401
    assert response.json() == {'detail': 'missing bearer token'}



def test_workspace_task_batch_create_forbids_member_role(tmp_path: Path) -> None:
    """普通 member 访问批量创建接口应返回 403。"""
    _init_test_db(tmp_path)
    workspace = str(tmp_path.resolve())

    with TestClient(app) as client:
        response = client.post(
            '/api/v1/workspaces/tasks/items/batch',
            headers={'Authorization': make_auth_headers(client, '19900000001', 'member')['Authorization']},
            json={
                'workspace_path': workspace,
                'items': [
                    {
                        'task_key': 'task-batch-002',
                        'title': '中文任务：成员越权测试',
                        'description': '验证 member 不能批量创建工作区任务。',
                        'status': 'todo',
                        'assignee': 'backend-dev',
                        'priority': 2,
                    }
                ],
            },
        )

    assert response.status_code == 403
    assert response.json() == {'detail': 'forbidden'}



def test_workspace_task_batch_create_allows_admin_and_leader(tmp_path: Path) -> None:
    """admin 与 leader 访问批量创建接口应成功创建任务。"""
    _init_test_db(tmp_path)
    workspace = str(tmp_path.resolve())

    with TestClient(app) as client:
        response = client.post(
            '/api/v1/workspaces/tasks/items/batch',
            headers={'Authorization': make_auth_headers(client, '19900000001', 'admin')['Authorization']},
            json={
                'workspace_path': workspace,
                'items': [
                    {
                        'task_key': 'task-batch-003',
                        'title': '中文任务：管理员批量创建',
                        'description': '验证管理员可以批量创建工作区任务。',
                        'status': 'ready',
                        'assignee': 'backend-dev',
                        'priority': 3,
                    },
                    {
                        'task_key': 'task-batch-004',
                        'title': '中文任务：团长批量创建',
                        'description': '验证团长可以批量创建工作区任务。',
                        'status': 'running',
                        'assignee': 'qa-dev',
                        'priority': 4,
                    },
                ],
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body['message'] == '批量创建成功'
    assert body['data']['count'] == 2
    assert [item['task_key'] for item in body['data']['items']] == ['task-batch-003', 'task-batch-004']
