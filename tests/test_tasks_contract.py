from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import app
from backend.routes import register_routes


def _client() -> TestClient:
    """创建测试客户端。"""
    return TestClient(app)


def test_tasks_progress_list_returns_default_items() -> None:
    """任务进度列表返回默认任务和总数。"""
    with _client() as client:
        response = client.get('/api/v1/tasks/progress')

    assert response.status_code == 200
    assert response.json()['data']['count'] == 3
    assert response.json()['data']['items'][1]['status'] == 'running'


def test_tasks_progress_detail_unknown_id_returns_404() -> None:
    """读取不存在的任务进度时返回 404。"""
    with _client() as client:
        response = client.get('/api/v1/tasks/progress/999')

    assert response.status_code == 404
    assert response.json() == {'detail': '任务不存在'}


def test_tasks_progress_simulate_rejects_steps_below_minimum() -> None:
    """模拟任务进度时，steps 小于最小值返回 422。"""
    with _client() as client:
        response = client.post('/api/v1/tasks/progress/simulate', json={'task_id': 1, 'steps': 1})

    assert response.status_code == 422
    assert response.json()['detail'] == '输入校验失败'


def test_tasks_progress_simulate_builds_two_step_timeline() -> None:
    """模拟任务进度时，steps=2 会生成首尾时间线。"""
    with _client() as client:
        response = client.post('/api/v1/tasks/progress/simulate', json={'task_id': 1, 'steps': 2})

    assert response.status_code == 200
    assert [item['percent'] for item in response.json()['data']['timeline']] == [0, 100]


def test_tasks_metadata_list_returns_sorted_items() -> None:
    """任务元数据列表按更新时间倒序返回。"""
    with _client() as client:
        response = client.get('/api/v1/tasks/metadata')

    assert response.status_code == 200
    assert response.json()['data']['count'] == 3
    assert response.json()['data']['items'][0]['task_id'] == 103


def test_tasks_metadata_detail_unknown_id_returns_404() -> None:
    """读取不存在的任务元数据时返回 404。"""
    with _client() as client:
        response = client.get('/api/v1/tasks/metadata/999')

    assert response.status_code == 404
    assert response.json()['detail'] == '任务不存在'


def test_task_board_intake_get_returns_default_rules() -> None:
    """任务看板 intake 默认规则接口返回三条卡片。"""
    with _client() as client:
        response = client.get('/api/v1/task-board/intake')

    assert response.status_code == 200
    body = response.json()['data']
    assert body['count'] == 3
    assert len(body['default_rules']) == 3


def test_task_board_intake_post_uses_keyword_priority() -> None:
    """创建看板 intake 时会根据关键词生成测试优先级内容。"""
    with _client() as client:
        response = client.post('/api/v1/task-board/intake', json={'topic': 'pytest 回归验证告警', 'module_hint': 'test'})

    assert response.status_code == 201
    card = response.json()['data']['cards'][0]
    assert card['module'] == 'test'
    assert card['default_fields']['module'] == 'test'


def test_task_board_intake_post_missing_topic_returns_422() -> None:
    """创建看板 intake 时缺少 topic 返回 422。"""
    with _client() as client:
        response = client.post('/api/v1/task-board/intake', json={'module_hint': 'test'})

    assert response.status_code == 422
    assert 'Field required' in response.json()['detail']


def test_register_routes_exposes_task_routes() -> None:
    """register_routes 会把任务路由挂到新应用上。"""
    temp_app = FastAPI()
    register_routes(temp_app)

    with TestClient(temp_app) as client:
        response = client.get('/api/v1/tasks/progress')

    assert response.status_code == 200
    assert response.json()['data']['count'] == 3
