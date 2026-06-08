from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app


client = TestClient(app)


def _auth_headers() -> dict[str, str]:
    return {'Authorization': 'Bearer demo-token'}


def test_worker_summary_shows_sorted_profiles_and_copy_hint() -> None:
    """The summary payload should be oriented around profile sorting."""
    response = client.get('/api/v1/workers/summary', headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()['data']
    assert isinstance(data['profile_order'], list)
    assert all(isinstance(name, str) for name in data['copyable_worker_names'])
    assert data['copy_hint'].startswith('点击 worker 名称')


def test_worker_recommendations_returns_structured_payload() -> None:
    """Worker recommendations should stay response-model friendly."""
    response = client.get('/api/v1/workers/recommendations', params={'workspace_path': '/tmp/demo', 'limit': 2})
    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['workspace_path'] == '/tmp/demo'
    assert isinstance(payload['data']['recommendations'], list)
