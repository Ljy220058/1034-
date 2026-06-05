from __future__ import annotations

import sqlite3
from pathlib import Path

import backend.database as database
from fastapi.testclient import TestClient

from backend.app import app


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
    response = client.get('/api/v1/workspaces/tasks?workspace=dir:/root/autodl-tmp/projects/hermes-swarm-lab', headers={'Authorization': 'Bearer 1:member:2099-01-01T00:00:00+00:00'})

    assert response.status_code == 200
    payload = response.json()['data']
    assert [item['task_key'] for item in payload] == ['task-2', 'task-1', 'task-3']
    assert payload[0]['metadata'] == {'tags': ['sqlite']}
    assert payload[0]['updated_at'] == '2026-06-07T08:10:00+00:00'


def test_workspace_task_discovery_endpoint_rejects_invalid_workspace_selector() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get('/api/v1/workspaces/tasks?workspace=bogus', headers={'Authorization': 'Bearer 1:member:2099-01-01T00:00:00+00:00'})

    assert response.status_code == 422
