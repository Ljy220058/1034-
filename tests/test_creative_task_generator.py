from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app
from backend.repository import connect, init_db


WORKER_FIXTURE = [
    ('wk-active-backend', '后端 API worker', 'active', '["api", "backend", "fastapi"]'),
    ('wk-paused-test', 'pytest 验证 worker', 'paused', '["pytest", "qa", "verify"]'),
    ('wk-disabled-review', '审查 worker', 'disabled', '["review", "audit"]'),
]


def _client_with_workers(tmp_path):
    db_path = tmp_path / 'task_board.db'
    init_db(db_path)
    with connect(db_path) as connection:
        for row in WORKER_FIXTURE:
            connection.execute(
                'INSERT INTO task_queue_workers (worker_key, name, status, capabilities) VALUES (?, ?, ?, ?)',
                row,
            )
    return TestClient(app, raise_server_exceptions=False)


def test_创意任务生成_管理员访问_返回两条标准化任务():
    """管理员访问创意任务生成接口时，返回两条标准化任务卡片。"""
    client = _client_with_workers(tmp_path=None)
