from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app, raise_server_exceptions=False)


def test_task_progress_list_returns_three_items() -> None:
    """任务流状态列表接口应返回结构化任务列表。"""
    response = client.get('/api/v1/tasks/progress')

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '成功'
    assert set(body.keys()) == {'data', 'message'}

    data = body['data']
    assert data['count'] == 3
    assert len(data['items']) == 3
    assert data['items'][0]['status'] == 'todo'
    assert all('progress' in item for item in data['items'])


def test_task_progress_detail_returns_single_item() -> None:
    """任务流状态详情接口应返回单条任务的结构化信息。"""
    response = client.get('/api/v1/tasks/progress/2')

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '成功'
    assert set(body.keys()) == {'data', 'message'}

    data = body['data']
    assert data['task_id'] == 2
    assert data['status'] == 'running'
    assert data['progress']['percent'] == 65
    assert data['progress']['remaining_steps'] == ['补齐回归测试', '联调接口', '手动验证']


def test_task_progress_simulation_returns_increasing_progress() -> None:
    """任务流状态进度推进入口应返回模拟进度序列。"""
    response = client.post('/api/v1/tasks/progress/simulate', json={'task_id': 1, 'steps': 4})

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '成功'
    assert set(body.keys()) == {'data', 'message'}

    data = body['data']
    assert data['task_id'] == 1
    assert data['steps'] == 4
    assert len(data['timeline']) == 4
    assert data['timeline'][0]['percent'] == 0
    assert data['timeline'][-1]['percent'] == 100
