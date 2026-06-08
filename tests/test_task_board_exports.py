from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app
from conftest import make_auth_headers
from backend.database import init_db
from backend.repository import connect

AUTH_HEADERS = None  # Replaced by make_auth_headers(client, ...) at call site
WORKERS = [
    ('wk-active-backend', '后端 API worker', 'active', '["api", "backend", "fastapi"]'),
    ('wk-paused-test', 'pytest 验证 worker', 'paused', '["pytest", "qa", "verify"]'),
    ('wk-disabled-review', '审查 worker', 'disabled', '["review", "audit"]'),
]


def _client(tmp_path):
    db_path = tmp_path / 'task_board.db'
    init_db(db_path)
    with connect(db_path) as connection:
        for row in WORKERS:
            connection.execute('INSERT INTO task_queue_workers (worker_key, name, status, capabilities) VALUES (?, ?, ?, ?)', row)
    return TestClient(app, raise_server_exceptions=False)


def test_创意任务生成_管理员访问_返回两条标准化任务(tmp_path):
    """管理员访问创意任务生成接口时返回两条标准化任务卡片。"""
    c = _client(tmp_path)
    response = c.get('/api/v1/creative-task-generator', headers={'Authorization': make_auth_headers(c, '19900000001', 'admin')['Authorization']})
    assert response.status_code == 200
    payload = response.json()['data']
    assert payload['count'] == 2
    assert [item['title'] for item in payload['tasks']] == ['中文创意：任务队列空闲 profile 摘要接口', '中文创意：后端任务卡片合规校验接口']


def test_创意任务生成_缺少认证_返回401(tmp_path):
    """未携带 Bearer 令牌访问时返回 401。"""
    response = _client(tmp_path).get('/api/v1/creative-task-generator')
    assert response.status_code == 401
    assert response.json()['detail'] == 'missing bearer token'


def test_创意任务生成_普通成员访问_返回403(tmp_path):
    """普通成员访问管理员接口时返回 403。"""
    c = _client(tmp_path)
    response = c.get('/api/v1/creative-task-generator', headers={'Authorization': make_auth_headers(c, '19900000002', 'member')['Authorization']})
    assert response.status_code == 403
    assert response.json()['detail'] == 'forbidden'


def test_创意任务生成_工作区路径为空_返回422(tmp_path):
    """工作区路径为空字符串时触发参数校验失败。"""
    c = _client(tmp_path)
    response = c.get('/api/v1/creative-task-generator', params={'workspace_path': ''}, headers={'Authorization': make_auth_headers(c, '19900000001', 'admin')['Authorization']})
    assert response.status_code == 422


def test_空闲后端推荐_管理员访问_返回按顺序的任务卡片(tmp_path):
    """管理员访问空闲后端推荐接口时按看板顺序返回任务卡片。"""
    c = _client(tmp_path)
    response = c.get('/api/v1/idle-backend-task-recommender', headers={'Authorization': make_auth_headers(c, '19900000001', 'admin')['Authorization']})
    assert response.status_code == 200
    payload = response.json()['data']
    assert payload['count'] == 2
    assert payload['fallback_used'] is False
    assert payload['idle_profiles'] == ['backend-dev']


def test_空闲后端推荐_缺少认证_返回401(tmp_path):
    """未认证访问空闲后端推荐接口时返回 401。"""
    response = _client(tmp_path).get('/api/v1/idle-backend-task-recommender')
    assert response.status_code == 401
    assert response.json()['detail'] == 'missing bearer token'


def test_看板工作者列表_管理员访问_返回active和paused统计(tmp_path):
    """管理员访问 worker 列表时仅返回 active/paused worker 及其统计。"""
    c = _client(tmp_path)
    response = c.get('/api/v1/task-board/workers', headers={'Authorization': make_auth_headers(c, '19900000001', 'admin')['Authorization']})
    assert response.status_code == 200
    payload = response.json()['data']
    assert payload['summary'] == {'total': 2, 'active': 1, 'paused': 1}
    assert [item['worker_key'] for item in payload['workers']] == ['wk-active-backend', 'wk-paused-test']


def test_看板工作者列表_缺少认证_返回401(tmp_path):
    """未认证访问 worker 列表时返回 401。"""
    response = _client(tmp_path).get('/api/v1/task-board/workers')
    assert response.status_code == 401
    assert response.json()['detail'] == 'missing bearer token'
