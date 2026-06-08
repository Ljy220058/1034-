from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app


class _FakeUser:
    role = 'leader'


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def _client(tmp_path: Path) -> TestClient:
    """Create a test client with an isolated database.

    Args:
        tmp_path: Temporary directory from pytest.

    Returns:
        FastAPI test client.
    """
    db_path = tmp_path / 'tasks.db'
    database.init_db(db_path)
    with database.connect(db_path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS workspace_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace TEXT NOT NULL,
                task_key TEXT NOT NULL,
                task_id TEXT,
                parent_task_id TEXT,
                title TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('todo', 'ready', 'running', 'blocked', 'done', 'archived')),
                assignee TEXT,
                priority INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT NOT NULL DEFAULT '{}',
                UNIQUE(workspace, task_key)
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS task_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace TEXT NOT NULL,
                task_id TEXT NOT NULL,
                blocked_count INTEGER NOT NULL DEFAULT 0,
                last_failure_reason TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                last_accepted_at TEXT,
                health_level TEXT NOT NULL DEFAULT 'healthy',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(workspace, task_id)
            )"""
        )
    client = TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
    from backend.routes import common

    app.dependency_overrides[common.get_current_user] = lambda: _FakeUser()
    return client


def test_report_summary_card_returns_api_response_shape(tmp_path: Path) -> None:
    """智能报表摘要接口应返回 ApiResponse 结构。"""
    client = _client(tmp_path)

    response = client.get(
        '/api/v1/reports/summary-card',
        params={
            'keywords': '跑团,训练 活动',
            'start_date': '2026-06-01',
            'end_date': '2026-06-06',
            'project': '夏季训练营',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '已生成智能报表摘要卡片'
    assert 'data' in payload
    assert payload['data']['filters']['keywords'] == ['跑团', '训练', '活动']
    assert len(payload['data']['cards']) == 3
    assert all('title' in card and 'points' in card and 'risk_tip' in card for card in payload['data']['cards'])


def test_report_summary_card_rejects_invalid_time_range(tmp_path: Path) -> None:
    """时间范围非法时应返回结构化中文错误。"""
    client = _client(tmp_path)

    response = client.get(
        '/api/v1/reports/summary-card',
        params={
            'keywords': '跑团',
            'start_date': '2026-06-07',
            'end_date': '2026-06-06',
        },
    )

    assert response.status_code == 422
    assert response.json() == {'detail': '开始时间不能晚于结束时间'}


def test_report_summary_card_rejects_empty_keywords(tmp_path: Path) -> None:
    """空关键词应返回结构化中文错误。"""
    client = _client(tmp_path)

    response = client.get('/api/v1/reports/summary-card', params={'keywords': '   '})

    assert response.status_code == 422
    assert response.json() == {'detail': '关键词不能为空'}
