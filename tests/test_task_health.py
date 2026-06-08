from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.task_board_models import upsert_workspace_task_item
from backend.worker_board import (
    get_task_health_by_task_id,
    list_workspace_task_health,
    upsert_task_health,
)


ROOT = Path(__file__).resolve().parents[1]


def _client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / 'task_health.db'
    database.init_db(db_path)
    # ensure workspace_tasks and task_health tables exist for API tests
    with database.connect(db_path) as conn:
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS workspace_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT NOT NULL, task_key TEXT NOT NULL,
                task_id TEXT, parent_task_id TEXT, title TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('todo', 'ready', 'running', 'blocked', 'done', 'archived')),
                assignee TEXT, priority INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, metadata TEXT NOT NULL DEFAULT '{}',
                UNIQUE(workspace, task_key)
            )'''
        )
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS task_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT NOT NULL, task_id TEXT NOT NULL,
                blocked_count INTEGER NOT NULL DEFAULT 0, last_failure_reason TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0, last_accepted_at TEXT,
                health_level TEXT NOT NULL DEFAULT 'healthy',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(workspace, task_id)
            )'''
        )
    return TestClient(app, raise_server_exceptions=False)


def _leader_token(client: TestClient) -> str:
    phone = f'15550007001-{uuid4().hex[:8]}'
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


def _insert_workspace_task(workspace: str, task_key: str = 'task-health-001', task_id: str = 't_health001') -> None:
    with database.connect() as connection:
        # ensure workspace_tasks table exists
        connection.execute(
            "CREATE TABLE IF NOT EXISTS workspace_tasks ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT NOT NULL, task_key TEXT NOT NULL,"
            "task_id TEXT, parent_task_id TEXT,"
            "title TEXT NOT NULL, status TEXT NOT NULL, assignee TEXT, priority INTEGER NOT NULL DEFAULT 0,"
            "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, metadata TEXT NOT NULL DEFAULT '{}',"
            "UNIQUE(workspace, task_key)"
            ")"
        )
        connection.execute(
            'INSERT INTO workspace_tasks(workspace, task_key, task_id, parent_task_id, title, status, assignee, priority, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (workspace, task_key, task_id, None, '验证任务健康度', 'running', 'backend-dev', 7, '2026-06-06T12:10:00+00:00', '{}'),
        )


def test_task_health_repository_reads_updates_and_filters_by_level(tmp_path: Path) -> None:
    database.init_db(tmp_path / 'repo_health.db')
    workspace = str(tmp_path.resolve())
    _insert_workspace_task(workspace)

    created = upsert_task_health(
        workspace_path=workspace,
        task_id='t_health001',
        health_level='at_risk',
        blocked_count=2,
        retry_count=3,
        last_failure_reason='pytest failed',
        last_accepted_at='2026-06-06T12:30:00+00:00',
    )

    assert created['task_id'] == 't_health001'
    assert created['health_level'] == 'at_risk'
    assert created['blocked_count'] == 2
    assert created['retry_count'] == 3
    assert created['last_failure_reason'] == 'pytest failed'
    assert created['last_accepted_at'] == '2026-06-06T12:30:00+00:00'

    updated = upsert_task_health(workspace_path=workspace, task_id='t_health001', health_level='healthy')
    assert updated['health_level'] == 'healthy'
    assert updated['blocked_count'] == 2

    assert get_task_health_by_task_id(workspace_path=workspace, task_id='t_health001') == updated
    assert list_workspace_task_health(workspace_path=workspace, health_level='healthy')[0]['task_id'] == 't_health001'
    assert list_workspace_task_health(workspace_path=workspace, health_level='blocked') == []


def test_task_health_api_returns_health_and_filters_board_without_breaking_existing_payload(tmp_path: Path) -> None:
    client = _client(tmp_path)
    token = _leader_token(client)
    headers = {'Authorization': f'Bearer {token}'}
    workspace = str(tmp_path.resolve())
    _insert_workspace_task(workspace)

    response = client.put(
        '/api/v1/workspaces/tasks/t_health001/health',
        params={'workspace_path': workspace},
        json={'health_level': 'blocked', 'blocked_count': 1, 'retry_count': 2, 'last_failure_reason': '人工验收未通过'},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()['data']['health_level'] == 'blocked'

    read_response = client.get(
        '/api/v1/workspaces/tasks/t_health001/health',
        params={'workspace_path': workspace},
        headers=headers,
    )
    assert read_response.status_code == 200
    assert read_response.json()['data']['task_id'] == 't_health001'

    board_response = client.get(
        '/api/v1/workers/board',
        params={'workspace_path': workspace, 'health_level': 'blocked'},
        headers=headers,
    )
    assert board_response.status_code == 200
    board = board_response.json()['data']
    assert board['filters']['health_level'] == 'blocked'
    assert board['tasks'][0]['task_key'] == 'task-health-001'
    assert board['tasks'][0]['health']['health_level'] == 'blocked'
    assert {'task_key', 'title', 'status', 'description', 'assignee', 'priority', 'updated_at', 'metadata'} <= set(board['tasks'][0])


def _headers(client: TestClient) -> dict[str, str]:
    return {'Authorization': f'Bearer {_leader_token(client)}'}


def _seed_task(workspace: str, task_key: str, status: str, assignee: str | None, health_level: str | None = None) -> None:
    upsert_workspace_task_item(
        workspace_path=workspace,
        task_key=task_key,
        title=f'{task_key} 任务',
        status=status,
        description=f'{task_key} 描述',
        assignee=assignee,
    )
    if health_level is not None:
        upsert_task_health(workspace_path=workspace, task_id=task_key, health_level=health_level)


def _board_task_keys(client: TestClient, workspace: str, headers: dict[str, str], **params: str) -> list[str]:
    response = client.get('/api/v1/workers/board', params={'workspace_path': workspace, **params}, headers=headers)
    assert response.status_code == 200, f'看板筛选应返回 200，实际响应：{response.text}'
    return [task['task_key'] for task in response.json()['data']['tasks']]


def test_任务看板筛选_健康等级为空_返回全部任务(tmp_path: Path) -> None:
    """未传健康等级时，任务看板应返回有健康记录和无健康记录的全部任务。"""
    # Arrange
    client, workspace = _client(tmp_path), str(tmp_path.resolve())
    headers = _headers(client)
    _seed_task(workspace, 'healthy-task', 'todo', 'backend-dev', 'healthy')
    _seed_task(workspace, 'unknown-health-task', 'doing', 'test-engineer')
    # Act
    task_keys = _board_task_keys(client, workspace, headers)
    # Assert
    assert set(task_keys) == {'healthy-task', 'unknown-health-task'}, '健康等级为空应不过滤任务'


def test_任务看板筛选_健康等级为高风险_只返回高风险任务(tmp_path: Path) -> None:
    """按高风险健康等级筛选时，只返回 at_risk 任务。"""
    # Arrange
    client, workspace = _client(tmp_path), str(tmp_path.resolve())
    headers = _headers(client)
    _seed_task(workspace, 'risk-task', 'todo', 'backend-dev', 'at_risk')
    _seed_task(workspace, 'healthy-task', 'todo', 'backend-dev', 'healthy')
    # Act
    task_keys = _board_task_keys(client, workspace, headers, health_level='at_risk')
    # Assert
    assert task_keys == ['risk-task'], '高风险筛选不能返回健康任务'


def test_任务看板筛选_负责人不存在_返回空列表(tmp_path: Path) -> None:
    """负责人不存在时，看板应稳定返回空任务列表。"""
    # Arrange
    client, workspace = _client(tmp_path), str(tmp_path.resolve())
    headers = _headers(client)
    _seed_task(workspace, 'assigned-task', 'todo', 'backend-dev', 'healthy')
    # Act
    task_keys = _board_task_keys(client, workspace, headers, assignee='missing-worker')
    # Assert
    assert task_keys == [], '不存在的负责人不应匹配任何任务'


def test_任务看板筛选_状态与健康等级组合_只返回同时匹配任务(tmp_path: Path) -> None:
    """状态和健康等级组合筛选时，只返回同时满足两个条件的任务。"""
    # Arrange
    client, workspace = _client(tmp_path), str(tmp_path.resolve())
    headers = _headers(client)
    _seed_task(workspace, 'blocked-risk-task', 'blocked', 'backend-dev', 'at_risk')
    _seed_task(workspace, 'todo-risk-task', 'todo', 'backend-dev', 'at_risk')
    _seed_task(workspace, 'blocked-healthy-task', 'blocked', 'backend-dev', 'healthy')
    # Act
    task_keys = _board_task_keys(client, workspace, headers, status='blocked', health_level='at_risk')
    # Assert
    assert task_keys == ['blocked-risk-task'], '组合筛选必须同时匹配状态和健康等级'


def test_task_health_migration_and_rollback_execute_cleanly(tmp_path: Path) -> None:
    db_path = tmp_path / 'migration_health.db'
    with sqlite3.connect(db_path) as connection:
        connection.executescript('CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        connection.executescript('CREATE TABLE IF NOT EXISTS task_health (id INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT NOT NULL, task_id TEXT NOT NULL, blocked_count INTEGER NOT NULL DEFAULT 0, last_failure_reason TEXT, retry_count INTEGER NOT NULL DEFAULT 0, last_accepted_at TEXT, health_level TEXT NOT NULL DEFAULT "healthy", created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        connection.executescript((ROOT / 'migrations' / '003_add_task_health.sql').read_text(encoding='utf-8'))
        indexes = {row[1] for row in connection.execute("PRAGMA index_list('task_health')").fetchall()}
        assert 'idx_task_health_workspace_task' in indexes
        assert 'idx_task_health_level' in indexes
        plan = connection.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM task_health WHERE health_level = 'blocked' ORDER BY datetime(updated_at) DESC"
        ).fetchall()
        assert any('idx_task_health_level' in str(row) for row in plan)
        connection.executescript((ROOT / 'migrations' / '003_add_task_health.rollback.sql').read_text(encoding='utf-8'))
        assert connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'task_health'").fetchone() is None
