from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.task_discovery import upsert_workspace_task


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def _client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / 'tasks.db'
    database.init_db(db_path)
    return TestClient(app, raise_server_exceptions=False)


def _leader_headers(client: TestClient) -> dict[str, str]:
    leader = client.post('/api/v1/auth/register', json={'name': 'Leader', 'phone': '15550003001', 'password': 'secret123', 'role': 'member'})
    assert leader.status_code == 201
    leader_id = leader.json()['data']['member']['id']
    with database.connect() as connection:
        connection.execute('UPDATE members SET role = ? WHERE id = ?', ('leader', leader_id))
    token = client.post('/api/v1/auth/login', json={'phone': '15550003001', 'password': 'secret123'}).json()['data']['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_task_discovery_returns_workspace_scoped_tasks_sorted_by_update(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))
    client = _client(tmp_path)
    headers = _leader_headers(client)

    now = datetime.now(timezone.utc)
    older = now - timedelta(hours=2)
    upsert_workspace_task(task_id='t_old', title='Old task', status='todo', updated_at=older, workspace_path=WORKSPACE_ROOT, assignee='backend-dev', metadata={'priority': 1})
    upsert_workspace_task(task_id='t_new', title='New task', status='running', updated_at=now, workspace_path=WORKSPACE_ROOT, assignee='backend-dev', parent_task_id='t_old', metadata={'priority': 2})

    response = client.get('/api/v1/workspaces/tasks', params={'workspace_path': str(WORKSPACE_ROOT), 'limit': 10}, headers=headers)
    assert response.status_code == 200
    payload = response.json()['data']
    assert [item['task_id'] for item in payload] == ['t_new', 't_old']
    assert payload[0]['workspace_path'] == str(WORKSPACE_ROOT.resolve())
    assert payload[0]['metadata'] == {'priority': 2}
    assert payload[1]['parent_task_id'] is None


def test_task_discovery_rejects_invalid_workspace_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))
    client = _client(tmp_path)
    headers = _leader_headers(client)

    response = client.get('/api/v1/workspaces/tasks', params={'workspace_path': '../outside', 'limit': 10}, headers=headers)
    assert response.status_code == 422
    assert response.json()['detail'] == 'invalid workspace path'


def test_task_discovery_filters_status_and_rejects_invalid_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(WORKSPACE_ROOT))
    client = _client(tmp_path)
    headers = _leader_headers(client)

    upsert_workspace_task(task_id='t_one', title='One', status='todo', workspace_path=WORKSPACE_ROOT)
    upsert_workspace_task(task_id='t_two', title='Two', status='done', workspace_path=WORKSPACE_ROOT)

    response = client.get('/api/v1/workspaces/tasks', params={'workspace_path': str(WORKSPACE_ROOT), 'status': 'done'}, headers=headers)
    assert response.status_code == 200
    assert [item['task_id'] for item in response.json()['data']] == ['t_two']

    invalid = client.get('/api/v1/workspaces/tasks', params={'workspace_path': str(WORKSPACE_ROOT), 'status': 'bogus'}, headers=headers)
    assert invalid.status_code == 422
    assert invalid.json()['detail'] == 'invalid task status filter'
