from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app
from conftest import make_auth_headers

client = TestClient(app)


def test_dashboard_digest_returns_chinese_summary_and_sections() -> None:
    """Dashboard digest should return structured Chinese response data."""
    response = client.get(
        '/api/v1/dashboard/digest',
        params={'workspace_path': '/root/autodl-tmp/projects/hermes-swarm-lab', 'limit': 5},
        headers={'Authorization': make_auth_headers(client, '19900000001', 'member')['Authorization']},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {'data', 'message'}
    assert body['message'] == '成功'

    data = body['data']
    assert data['workspace_path'] == '/root/autodl-tmp/projects/hermes-swarm-lab'
    assert 'summary' in data
    assert 'workers' in data
    assert 'task_health' in data
    assert 'snapshot' in data
    assert 'recommendations' in data
    assert isinstance(data['summary']['workers_total'], int)
    assert isinstance(data['workers']['items'], list)
    assert isinstance(data['task_health']['items'], list)
    assert isinstance(data['recommendations'], list)


def test_dashboard_digest_filters_health_level() -> None:
    """Dashboard digest should accept a health level filter."""
    response = client.get(
        '/api/v1/dashboard/digest',
        params={
            'workspace_path': '/root/autodl-tmp/projects/hermes-swarm-lab',
            'health_level': 'blocked',
            'limit': 5,
        },
        headers={'Authorization': make_auth_headers(client, '19900000001', 'member')['Authorization']},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {'data', 'message'}
    assert all(row['health_level'] == 'blocked' for row in body['data']['task_health']['items'])
