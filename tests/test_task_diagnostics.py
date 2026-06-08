from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.task_diagnostics import build_task_diagnostic_suggestion
from backend.task_board_models import upsert_workspace_task_item


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(tmp_path.resolve()))
    database.init_db(tmp_path / 'task_diagnostics.db')
    return TestClient(app, raise_server_exceptions=False)


def _leader_token(client: TestClient) -> str:
    phone = f'15550008001-{uuid4().hex[:8]}'
    created = client.post(
        '/api/v1/auth/register',
        json={'name': 'Leader', 'phone': phone, 'password': 'secret123', 'role': 'member'},
    )
    assert created.status_code == 201
    member_id = created.json()['data']['member']['id']
    with database.connect() as connection:
        connection.execute('UPDATE members SET role = ? WHERE id = ?', ('leader', member_id))
    logged_in = client.post('/api/v1/auth/login', json={'phone': phone, 'password': 'secret123'})
    assert logged_in.status_code == 200
    return logged_in.json()['data']['access_token']


def test_task_diagnostic_suggestion_distinguishes_blocked_triage_and_todo() -> None:
    blocked = build_task_diagnostic_suggestion(
        {
            'task_id': 't_blocked',
            'title': '后端接口 pytest 失败',
            'description': 'FastAPI 接口返回 500',
            'status': 'blocked',
            'recent_results': ['pytest tests/test_api.py 失败'],
        }
    )
    triage = build_task_diagnostic_suggestion(
        {
            'task_id': 't_triage',
            'title': '多次失败的登录任务',
            'description': '需要重新整理规格',
            'status': 'triage',
        }
    )
    todo = build_task_diagnostic_suggestion(
        {
            'task_id': 't_todo',
            'title': '前端页面补充空状态',
            'description': 'React UI 缺少示例输入',
            'status': 'todo',
        }
    )

    assert blocked['status'] == 'blocked'
    assert 'blocked' in blocked['problem_summary']
    assert blocked['recommended_assignee'] in {'backend-dev', 'qa-tester'}
    assert '原始错误日志' in blocked['missing_information'][0]
    assert triage['status'] == 'triage'
    assert '重建' in triage['next_step']
    assert todo['status'] == 'todo'
    assert todo['non_mutating'] is True
    assert {'problem_summary', 'recommended_assignee', 'action_suggestions'} <= set(todo)


def test_blocked_task_diagnostic_includes_four_self_recovery_guides() -> None:
    suggestion = build_task_diagnostic_suggestion(
        {
            'task_id': 't_blocked_guides',
            'title': '阻塞任务自助恢复',
            'description': '需要判断上下文、测试、权限和依赖问题',
            'status': 'blocked',
            'recent_results': ['pytest 失败且缺少 API token，上游任务未完成'],
        }
    )

    guides = suggestion['self_recovery_guides']
    assert len(guides) >= 4
    categories = {guide['category'] for guide in guides}
    assert {'缺少上下文', '测试失败', '权限问题', '依赖任务未完成'} <= categories
    for guide in guides:
        assert guide['phenomenon']
        assert guide['recommended_action']
        assert guide['copyable_command_or_entry']
        assert any('\u4e00' <= char <= '\u9fff' for char in guide['title'])
        assert any('\u4e00' <= char <= '\u9fff' for char in guide['phenomenon'])


def test_task_diagnostics_api_returns_non_mutating_chinese_payload(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    token = _leader_token(client)
    headers = {'Authorization': f'Bearer {token}'}
    workspace = str(tmp_path.resolve())

    upsert_workspace_task_item(
        workspace_path=workspace,
        task_key='task-blocked',
        title='后端接口阻塞',
        status='blocked',
        description='API pytest 失败',
        assignee='backend-dev',
        priority=9,
        metadata={'recent_results': ['pytest tests/test_api.py::test_x 失败'], 'tags': ['后端']},
    )
    upsert_workspace_task_item(
        workspace_path=workspace,
        task_key='task-todo',
        title='补充前端示例',
        status='todo',
        description='需要最小输入样例',
        assignee=None,
        priority=3,
        metadata={'summary': '缺少示例输入'},
    )

    response = client.get(
        '/api/v1/workspaces/tasks/diagnostics',
        params={'workspace_path': '.', 'limit': 10},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '成功'
    data = body['data']
    assert data['non_mutating'] is True
    assert data['summary']['diagnostic_count'] == 2
    assert data['summary']['blocked_count'] == 1
    diagnostics = {item['task_id']: item for item in data['diagnostics']}
    assert diagnostics['task-blocked']['status'] == 'blocked'
    assert diagnostics['task-blocked']['recent_results_used'] == ['pytest tests/test_api.py::test_x 失败']
    assert diagnostics['task-todo']['status'] == 'todo'
    assert diagnostics['task-todo']['recommended_assignee']
