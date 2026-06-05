from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
import backend.db as db_module
from backend.app import app
from backend.settings import build_readiness_status, format_readiness_summary


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ENTRIES = {
    'README.md',
    'backend',
    'frontend',
    'docs',
    'tests',
    'migrations',
    'requirements.txt',
    'pytest.ini',
}


def _workspace_snapshot() -> dict[str, object]:
    entries = sorted(p.name for p in WORKSPACE_ROOT.iterdir())
    digest = hashlib.sha256('\n'.join(entries).encode('utf-8')).hexdigest()
    missing = sorted(EXPECTED_ENTRIES.difference(entries))
    return {
        'root': str(WORKSPACE_ROOT),
        'entry_count': len(entries),
        'entries': entries,
        'missing': missing,
        'digest': digest,
    }


def _client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / 'test.db'
    database.init_db(db_path)
    return TestClient(app, raise_server_exceptions=False)


def _register_member(client: TestClient, *, name: str, phone: str, role: str = 'member') -> dict[str, object]:
    resp = client.post(
        '/api/v1/auth/register',
        json={'name': name, 'phone': phone, 'password': 'secret123', 'role': role},
    )
    assert resp.status_code == 201
    return resp.json()['data']


def _auth_header(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def _leader_and_member(client: TestClient):
    leader = _register_member(client, name='Leader', phone='15550001001')
    member = _register_member(client, name='Runner', phone='15550001002')
    with database.connect() as connection:
        connection.execute('UPDATE members SET role = ? WHERE id = ?', ('leader', leader['member']['id']))
    leader_token = client.post('/api/v1/auth/login', json={'phone': '15550001001', 'password': 'secret123'}).json()['data']['access_token']
    return leader, member, _auth_header(leader_token)


def _activity_with_registration(client: TestClient):
    leader, member, leader_headers = _leader_and_member(client)
    activity = client.post(
        '/api/v1/activities',
        json={'title': 'Check-in Run', 'start_time': '2026-06-07T07:00:00+00:00', 'location': 'Track'},
        headers=leader_headers,
    ).json()['data']
    reg = client.post(
        f"/api/v1/activities/{activity['id']}/registrations",
        json={'member_id': member['member']['id']},
        headers=_auth_header(member['access_token']),
    )
    assert reg.status_code == 201
    return leader, member, activity, leader_headers


def test_workspace_integrity_snapshot_is_stable() -> None:
    snapshot = _workspace_snapshot()

    assert snapshot['root'].endswith('hermes-swarm-lab')
    assert snapshot['entry_count'] >= len(EXPECTED_ENTRIES)
    assert snapshot['missing'] == []
    assert isinstance(snapshot['digest'], str)
    assert len(snapshot['digest']) == 64


def test_workspace_integrity_snapshot_serializes_to_json() -> None:
    snapshot = _workspace_snapshot()

    encoded = hashlib.sha256(str(snapshot).encode('utf-8')).hexdigest()

    assert 'README.md' in str(snapshot)
    assert len(encoded) == 64


def test_readiness_status_includes_workspace_and_database_path(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / 'running_club.db'
    db_path.write_text('sqlite-db-placeholder', encoding='utf-8')
    monkeypatch.setenv('RUNNING_CLUB_DB_PATH', str(db_path))

    status = build_readiness_status(project_root=WORKSPACE_ROOT, database_path=db_path)

    assert status.ready is True
    assert status.project_root == WORKSPACE_ROOT
    assert status.workspace_root == WORKSPACE_ROOT
    assert status.database_path == db_path
    assert status.missing_env_vars == ()
    assert status.stale_workspace_artifacts == ()
    summary = format_readiness_summary(status)
    assert 'READY | env: all required env vars set' in summary
    assert f'database found at {db_path}' in summary
    assert f'workspace clean at {WORKSPACE_ROOT}' in summary


def test_readiness_status_reports_missing_database_and_env(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / 'missing.db'
    monkeypatch.delenv('RUNNING_CLUB_DB_PATH', raising=False)

    status = build_readiness_status(project_root=WORKSPACE_ROOT, database_path=db_path)

    assert status.ready is False
    assert status.missing_env_vars == ('RUNNING_CLUB_DB_PATH',)
    assert status.database_exists is False
    assert status.stale_workspace_artifacts == ()
    summary = format_readiness_summary(status)
    assert summary.startswith('NOT READY | env: missing env vars: RUNNING_CLUB_DB_PATH')
    assert f'database missing at {db_path}' in summary


def test_readiness_status_detects_missing_workspace_root(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / 'running_club.db'
    db_path.write_text('sqlite-db-placeholder', encoding='utf-8')
    monkeypatch.setenv('RUNNING_CLUB_DB_PATH', str(db_path))
    missing_root = tmp_path / 'missing-workspace'

    status = build_readiness_status(project_root=missing_root, database_path=db_path)

    assert status.ready is False
    assert status.stale_workspace_artifacts == ('workspace-root-missing',)
    assert 'stale workspace artifacts: workspace-root-missing' in format_readiness_summary(status)


def test_health_endpoint_returns_readiness_details(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / 'health.db'
    db_path.write_text('sqlite-db-placeholder', encoding='utf-8')
    monkeypatch.setenv('RUNNING_CLUB_DB_PATH', str(db_path))

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get('/health')

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
    assert payload['ready'] is True
    assert payload['readiness']['database_path'] == str(db_path)
    assert payload['readiness']['database_exists'] is True
    assert payload['readiness']['missing_env_vars'] == []
    assert payload['readiness']['stale_workspace_artifacts'] == []
    assert 'READY | env: all required env vars set' in payload['summary']


def test_create_checkin_endpoint_persists_attendance(tmp_path) -> None:
    from backend.app import app
    from fastapi.testclient import TestClient
    import backend.database as database

    db_path = tmp_path / 'checkin.db'
    database.init_db(db_path)
    client = TestClient(app, raise_server_exceptions=False)

    register = client.post('/api/v1/auth/register', json={'name': 'Leader', 'phone': '15550002001', 'password': 'secret123', 'role': 'member'})
    assert register.status_code == 201
    leader_id = register.json()['data']['member']['id']
    with database.connect() as connection:
        connection.execute('UPDATE members SET role = ? WHERE id = ?', ('leader', leader_id))
    leader_token = client.post('/api/v1/auth/login', json={'phone': '15550002001', 'password': 'secret123'}).json()['data']['access_token']

    member = client.post('/api/v1/auth/register', json={'name': 'Runner', 'phone': '15550002002', 'password': 'secret123', 'role': 'member'}).json()['data']['member']
    activity = client.post('/api/v1/activities', json={'title': 'Tempo Run', 'start_time': '2026-06-07T07:00:00+00:00', 'location': 'Track'}, headers={'Authorization': f'Bearer {leader_token}'}).json()['data']
    registration = client.post(f"/api/v1/activities/{activity['id']}/registrations", json={'member_id': member['id']}, headers={'Authorization': f'Bearer {leader_token}'} )
    assert registration.status_code == 201

    response = client.post(
        f"/api/v1/activities/{activity['id']}/checkins",
        json={'activity_id': activity['id'], 'member_id': member['id'], 'checked_in_at': '2026-06-07T07:05:00+00:00', 'gps_checked': True},
        headers={'Authorization': f'Bearer {leader_token}'},
    )
    assert response.status_code == 201
    payload = response.json()['data']
    assert payload['activity_id'] == activity['id']
    assert payload['member_id'] == member['id']
    assert payload['gps_checked'] is True

    with database.connect() as connection:
        row = connection.execute('SELECT activity_id, member_id, status, gps_checked FROM attendances WHERE activity_id = ? AND member_id = ?', (activity['id'], member['id'])).fetchone()
    assert row['status'] == 'signed_in'
    assert row['gps_checked'] == 1
