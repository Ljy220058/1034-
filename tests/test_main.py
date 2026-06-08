from __future__ import annotations

import sqlite3
from pathlib import Path

import backend.database as database
from fastapi.testclient import TestClient

from backend.app import app
from conftest import make_auth_headers


def _ensure_workspace_tasks_table(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS workspace_tasks (
                workspace TEXT NOT NULL,
                task_key TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                assignee TEXT,
                priority INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}'
            )
            '''
        )
        connection.commit()


def test_workspace_sync_healthcheck_returns_ok_status_and_readiness_snapshot() -> None:
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get('/health/sync')

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] in {'ok', 'degraded'}
    assert payload['workspace']['project_root'].endswith('/hermes-swarm-lab')
    assert 'ready' in payload
    assert 'summary' in payload


def test_workspace_task_discovery_endpoint_returns_sorted_normalized_tasks(tmp_path) -> None:
    db_path = tmp_path / 'workspace_tasks.db'
    database.init_db(db_path)
    _ensure_workspace_tasks_table(db_path)
    with database.connect(db_path) as connection:
        connection.execute(
            'INSERT INTO workspace_tasks (workspace, task_key, title, status, assignee, priority, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            ('/root/autodl-tmp/projects/hermes-swarm-lab', 'task-1', 'Alpha Task', 'running', 'alice', 5, '2026-06-07T07:10:00+00:00', '{"tags": ["api"]}'),
        )
        connection.execute(
            'INSERT INTO workspace_tasks (workspace, task_key, title, status, assignee, priority, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            ('/root/autodl-tmp/projects/hermes-swarm-lab', 'task-2', 'Beta Task', 'ready', 'bob', 1, '2026-06-07T08:10:00+00:00', '{"tags": ["sqlite"]}'),
        )
        connection.execute(
            'INSERT INTO workspace_tasks (workspace, task_key, title, status, assignee, priority, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            ('/root/autodl-tmp/projects/hermes-swarm-lab', 'task-3', 'Gamma Task', 'archived', None, 0, '2026-06-06T08:10:00+00:00', '{}'),
        )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get('/api/v1/workspaces/tasks?workspace_path=dir:/root/autodl-tmp/projects/hermes-swarm-lab', headers={'Authorization': make_auth_headers(client, '19900000001', 'member')['Authorization']})

    assert response.status_code == 200
    payload = response.json()['data']
    assert [item['task_key'] for item in payload] == ['task-2', 'task-1', 'task-3']
    assert payload[0]['metadata'] == {'tags': ['sqlite']}
    assert payload[0]['updated_at'] == '2026-06-07T08:10:00+00:00'


def test_workspace_task_discovery_endpoint_rejects_invalid_workspace_selector() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get('/api/v1/workspaces/tasks?workspace_path=bogus', headers={'Authorization': make_auth_headers(client, '19900000001', 'member')['Authorization']})

    assert response.status_code == 422


def test_task_routes_return_api_response_message_and_data_shape() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post('/api/v1/workspaces/tasks/items')

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert 'data' in payload


def test_task_metadata_endpoint_returns_summary_labels_and_updated_at() -> None:
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get('/api/v1/tasks/metadata')

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['count'] == 3
    first_item = payload['data']['items'][0]
    assert {'task_id', 'summary', 'status', 'labels', 'updated_at'} <= set(first_item)
    assert first_item['updated_at'].endswith('+00:00')


def test_task_metadata_endpoint_rejects_missing_task_with_structured_error() -> None:
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get('/api/v1/tasks/metadata/999999')

    assert response.status_code == 404
    assert response.json() == {'detail': '任务不存在'}


def test_idle_task_summary_endpoints_return_metadata_preview_and_filter_validation() -> None:
    client = TestClient(app, raise_server_exceptions=False)

    summary_response = client.get('/api/v1/idle-task-summary/summary')
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload['message'] == '已返回空闲后端任务摘要'
    assert {'workspace_path', 'generated_at', 'summary', 'idle_workers', 'pending_tasks', 'recent_block_reasons', 'dispatch_recommendations'} <= set(summary_payload['data'])
    assert {'idle_workers', 'pending_tasks', 'blocked_tasks', 'todo_tasks', 'ready_tasks', 'running_tasks', 'dispatch_recommendations'} <= set(summary_payload['data']['summary'])

    sidebar_response = client.get('/api/v1/idle-task-summary/sidebar?status=bogus')
    assert sidebar_response.status_code == 422
    assert sidebar_response.json() == {'detail': '状态筛选参数无效'}


def test_task_auto_archive_endpoint_returns_preview_and_archive_statistics(tmp_path: Path) -> None:
    db_path = tmp_path / 'auto_archive.db'
    database.init_db(db_path)
    _ensure_workspace_tasks_table(db_path)
    with database.connect(db_path) as connection:
        connection.execute(
            'INSERT INTO workspace_tasks (workspace, task_key, title, status, assignee, priority, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            ('/root/autodl-tmp/projects/hermes-swarm-lab', 'recent-done', 'Recent Done Task', 'done', 'alice', 3, '2026-06-06T12:30:00+00:00', '{"completed_at": "2026-06-06T12:30:00+00:00"}'),
        )
        connection.execute(
            'INSERT INTO workspace_tasks (workspace, task_key, title, status, assignee, priority, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            ('/root/autodl-tmp/projects/hermes-swarm-lab', 'stale-done', 'Stale Done Task', 'done', 'bob', 2, '2026-06-04T12:30:00+00:00', '{"completed_at": "2026-06-04T12:30:00+00:00"}'),
        )
        connection.execute(
            'INSERT INTO workspace_tasks (workspace, task_key, title, status, assignee, priority, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            ('/root/autodl-tmp/projects/hermes-swarm-lab', 'already-archived', 'Already Archived', 'archived', 'carol', 1, '2026-06-04T12:30:00+00:00', '{}'),
        )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        '/api/v1/tasks/auto-archive',
        json={'workspace_path': 'dir:/root/autodl-tmp/projects/hermes-swarm-lab', 'threshold_days': 1, 'dry_run': True},
        headers={'Authorization': make_auth_headers(client, '19900000001', 'member')['Authorization']},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['settings']['threshold_days'] == 1
    assert payload['data']['settings']['dry_run'] is True
    assert payload['data']['summary']['candidates'] == 1
    assert payload['data']['summary']['eligible'] == 1
    assert payload['data']['summary']['archived'] == 0
    assert payload['data']['tasks'][0]['task_key'] == 'stale-done'
    assert payload['data']['tasks'][0]['next_status'] == 'archived'
    assert payload['data']['tasks'][0]['reason'] == '完成时间超过归档阈值'
