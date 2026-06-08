from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app


client = TestClient(app, raise_server_exceptions=False)


def test_tasks_progress_正常请求_返回任务列表和数量():
    """任务进度列表接口返回成功状态、数量和任务项。"""
    # Arrange
    # Act
    response = client.get('/api/v1/tasks/progress')
    # Assert
    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['count'] == len(payload['data']['items'])


def test_tasks_progress_路径参数不存在_返回404():
    """不存在的任务进度详情应返回 404。"""
    # Arrange
    # Act
    response = client.get('/api/v1/tasks/progress/999999')
    # Assert
    assert response.status_code == 404
    assert response.json() == {'detail': '任务不存在'}


def test_tasks_progress_simulate_缺少必填字段_返回422():
    """模拟任务进度时缺少必填字段会触发 422 校验错误。"""
    # Arrange
    # Act
    response = client.post('/api/v1/tasks/progress/simulate', json={'steps': 3})
    # Assert
    assert response.status_code == 422


def test_tasks_progress_simulate_steps太小_返回422():
    """steps 小于最小值时应被 Pydantic 拒绝。"""
    # Arrange
    # Act
    response = client.post('/api/v1/tasks/progress/simulate', json={'task_id': 1, 'steps': 1})
    # Assert
    assert response.status_code == 422


def test_tasks_metadata_正常请求_返回元数据列表():
    """任务元数据列表接口返回成功状态和元数据条目。"""
    # Arrange
    # Act
    response = client.get('/api/v1/tasks/metadata')
    # Assert
    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['count'] == len(payload['data']['items'])


def test_tasks_metadata_不存在任务_返回404():
    """读取不存在的任务元数据时返回 404。"""
    # Arrange
    # Act
    response = client.get('/api/v1/tasks/metadata/999999')
    # Assert
    assert response.status_code == 404
    assert response.json() == {'detail': '任务不存在'}
