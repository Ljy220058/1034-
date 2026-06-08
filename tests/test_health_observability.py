from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app
from conftest import make_auth_headers
from backend.worker_board import upsert_task_health
from backend.worker_recommendations import upsert_queue_worker

client = TestClient(app)


def test_root_returns_message_payload() -> None:
    """Root endpoint should return the documented message payload.

    Returns:
        None.
    """
    response = client.get('/')

    assert response.status_code == 200
    payload = response.json()
    assert payload == {'message': '1034 Running Club backend is running. Visit /docs for the API documentation.'}


def test_health_returns_observability_fields() -> None:
    """Health endpoint should expose readiness and workspace observability.

    Returns:
        None.
    """
    response = client.get('/health')

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] in {'ok', 'degraded'}
    assert isinstance(payload['ready'], bool)
    assert isinstance(payload['summary'], str)
    assert 'workspace' in payload
    assert 'readiness' in payload
    assert 'stale_workspace_artifacts' in payload['workspace']
    assert 'missing_env_vars' in payload['readiness']


def test_health_ready_returns_compact_snapshot() -> None:
    """Compact readiness endpoint should expose structured JSON only.

    Returns:
        None.
    """
    response = client.get('/health/ready')

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload['ready'], bool)
    assert isinstance(payload['missing_env_vars'], list)
    assert isinstance(payload['summary'], str)
    assert 'workspace_root' in payload


def test_health_sync_matches_health_shape() -> None:
    """Sync health endpoint should mirror the full health payload shape.

    Returns:
        None.
    """
    response = client.get('/health/sync')

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] in {'ok', 'degraded'}
    assert isinstance(payload['ready'], bool)
    assert 'workspace' in payload
    assert 'readiness' in payload


def test_worker_digest_returns_api_response_shape() -> None:
    """Worker digest endpoint should return a structured auth error.

    Returns:
        None.
    """
    response = client.get('/api/v1/workers/digest')

    assert response.status_code == 401
    assert response.json() == {'detail': 'missing bearer token'}


def test_worker_board_and_health_and_digest_are_registered() -> None:
    """Worker endpoints should be registered on the application.

    Returns:
        None.
    """
    board_response = client.get('/api/v1/workers/board')
    health_response = client.get('/api/v1/workers/health')
    digest_response = client.get('/api/v1/workers/digest')

    assert board_response.status_code == 401
    assert health_response.status_code == 401
    assert digest_response.status_code == 401
    assert 'detail' in board_response.json()
    assert 'detail' in health_response.json()
    assert 'detail' in digest_response.json()


def test_worker_digest_returns_compact_summary_payload(tmp_path, monkeypatch) -> None:
    """Worker digest endpoint should expose summary, snapshot, alerts, and health rows.

    Args:
        tmp_path: Temporary directory from pytest.
        monkeypatch: Pytest environment patch helper.
    """
    monkeypatch.setenv('HERMES_KANBAN_WORKSPACE', str(tmp_path))
    headers = {'Authorization': make_auth_headers(client, '19900000001', 'leader')['Authorization']}

    response = client.get('/api/v1/workers/digest', params={'workspace_path': str(tmp_path)}, headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert set(payload['data']) >= {'summary', 'snapshot', 'health_rows', 'alerts'}
    summary = payload['data']['summary']
    assert summary['worker_count'] == 0
    assert summary['duplicate_alert_count'] == 0
    assert summary['idle_worker_count'] == 0
    assert summary['task_health_count'] == 0
    assert payload['data']['snapshot']['workspace_path'] == str(tmp_path)
    assert payload['data']['alerts'] == []

    upsert_task_health(workspace_path=tmp_path, task_id='task-backend', health_level='blocked', blocked_count=2, retry_count=1, last_failure_reason='队列阻塞', last_accepted_at=None)
    upsert_task_health(workspace_path=tmp_path, task_id='task-frontend', health_level='healthy', blocked_count=0, retry_count=0, last_failure_reason=None, last_accepted_at=None)

    response = client.get('/api/v1/workers/digest', params={'workspace_path': str(tmp_path)}, headers=headers)

    assert response.status_code == 200
    payload = response.json()
    summary = payload['data']['summary']
    assert summary['task_health_count'] == 2
    assert summary['duplicate_alert_count'] == 1
    assert payload['data']['alerts'][0]['type'] == 'health_warning'


def test_worker_dashboard_summary_and_sidebar_return_alert_friendly_payload(tmp_path) -> None:
    """Worker dashboard routes should expose queue health and sidebar cards.

    Args:
        tmp_path: Temporary directory from pytest.
    """
    workspace = str(tmp_path)
    upsert_queue_worker('backend-dev', '后端 worker', 'active', ['FastAPI', 'SQLite', 'API'])
    upsert_queue_worker('test-worker', '测试 worker', 'paused', ['pytest', 'QA'])
    upsert_task_health(workspace_path=workspace, task_id='task-001', health_level='blocked', blocked_count=3, retry_count=2, last_failure_reason='重试失败', last_accepted_at=None)

    summary_response = client.get('/api/v1/dashboard/digest/summary', params={'workspace_path': workspace})
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload['message'] == '已返回空闲度概览面板'
    assert summary_payload['data']['workspace_path'] == str(tmp_path.resolve())
    assert 'summary' in summary_payload['data']
    assert 'workers' in summary_payload['data']
    assert isinstance(summary_payload['data']['workers'], list)

    sidebar_response = client.get('/api/v1/worker-dashboard/sidebar', params={'workspace_path': workspace, 'status': 'running'})
    assert sidebar_response.status_code == 200
    sidebar_payload = sidebar_response.json()
    assert sidebar_payload['message'] == '已返回 running 任务侧栏'
    assert sidebar_payload['data']['status_filter'] == 'running'
    assert 'tasks' in sidebar_payload['data']
    assert isinstance(sidebar_payload['data']['summary']['total'], int)
