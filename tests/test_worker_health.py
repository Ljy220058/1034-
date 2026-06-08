from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app
from backend.repository import Member
from backend.routes.common import CurrentUser, get_current_user
from backend.worker_board import build_task_health_summary, upsert_task_health

client = TestClient(app, raise_server_exceptions=False)


def _leader_user() -> CurrentUser:
    member = Member(
        id=1,
        name='测试团长',
        phone=None,
        role='leader',
        running_years=3,
        pace=None,
        usual_distance_km=None,
        training_goal=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    return CurrentUser(id=1, role='leader', member=member)


def test_worker_health_endpoint_groups_task_health_by_status(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / 'test.db'
    monkeypatch.setenv('RUNNING_CLUB_DB_PATH', str(db_path))
    database.init_db(db_path)

    workspace = tmp_path / 'workspace-a'
    workspace.mkdir()

    upsert_task_health(workspace_path=workspace, task_id='task-ready', health_level='healthy')
    upsert_task_health(workspace_path=workspace, task_id='task-running', health_level='at_risk')
    upsert_task_health(workspace_path=workspace, task_id='task-blocked', health_level='blocked')
    upsert_task_health(workspace_path=workspace, task_id='task-done', health_level='failing')

    user = _leader_user()
    setattr(user, 'workspace_path', str(workspace))
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.get('/api/v1/workers/health')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['workspace_path'] == str(workspace)
    assert payload['data']['counts'] == {'ready': 0, 'running': 0, 'blocked': 0, 'done': 0}
    assert payload['data']['total'] == 4
    assert len(payload['data']['recent_tasks']) == 4


def test_build_task_health_summary_returns_zero_counts_for_empty_workspace(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / 'empty.db'
    monkeypatch.setenv('RUNNING_CLUB_DB_PATH', str(db_path))
    database.init_db(db_path)
    workspace = tmp_path / 'workspace-empty'
    workspace.mkdir()

    summary = build_task_health_summary(workspace)

    assert summary['workspace_path'] == str(workspace)
    assert summary['counts'] == {'ready': 0, 'running': 0, 'blocked': 0, 'done': 0}
    assert summary['total'] == 0
