from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app


def _client(tmp_path: Path) -> TestClient:
    database.init_db(tmp_path / 'workspace_path_security.db')
    return TestClient(app, raise_server_exceptions=False)


def _leader_headers(client: TestClient) -> dict[str, str]:
    phone = f'15550009001-{uuid4().hex[:8]}'
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
    return {'Authorization': f"Bearer {logged_in.json()['data']['access_token']}"}


def test_workspace_api_rejects_traversal_absolute_hidden_and_outside_paths(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(workspace))
    client = _client(tmp_path)
    headers = _leader_headers(client)

    malicious_paths = [
        '../outside.txt',
        '../../etc/passwd',
        '/etc/passwd',
        '.env',
        'docs/.secret.md',
    ]
    endpoints = [
        ('/api/v1/workspaces/board', 'get'),
        ('/api/v1/workers/board', 'get'),
        ('/api/v1/workspaces/tasks/diagnostics', 'get'),
        ('/api/v1/workers/idle-recommendations', 'get'),
        ('/api/v1/workspaces/tasks/t_path_guard/health', 'get'),
        ('/api/v1/workspaces/tasks/t_path_guard/health', 'put'),
    ]

    for unsafe_path in malicious_paths:
        for endpoint, method in endpoints:
            kwargs = {'params': {'workspace_path': unsafe_path}, 'headers': headers}
            if method == 'put':
                kwargs['json'] = {'health_level': 'healthy'}
            response = getattr(client, method)(endpoint, **kwargs)
            assert response.status_code == 422
            assert response.json()['detail'] == '工作区路径不合法：禁止访问工作区外部、绝对路径或隐藏文件路径'


def test_workspace_api_allows_legitimate_workspace_path(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(workspace))
    client = _client(tmp_path)
    headers = _leader_headers(client)

    response = client.get(
        '/api/v1/workers/idle-recommendations',
        params={'workspace_path': str(workspace), 'limit': 5},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()['data']['risk_note'] == '路径参数已限制在工作区内，拒绝 ../、/etc/passwd、隐藏文件路径和非工作区文件访问，避免附件/文档路径穿越导致敏感文件泄露。'
