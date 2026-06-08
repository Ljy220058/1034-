from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_batch_route_creative_cards_creates_workers_and_skips_duplicates() -> None:
    """批量路由应创建可识别任务并跳过重复项。

    Returns:
        None.
    """
    response = client.post(
        '/api/v1/creative-cards/batch-route',
        json={
            'items': [
                {'description': '请帮我处理后端接口和数据库迁移', 'task_type': '后端'},
                {'description': '请帮我处理后端接口和数据库迁移', 'task_type': '后端'},
                {'description': '需要补一版 README 使用说明', 'task_type': '文档'},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['message'] == '成功'
    assert payload['data']['summary'] == {'total': 3, 'created': 2, 'failed': 0, 'duplicates': 1}
    assert payload['data']['results'][0]['status'] == 'created'
    assert payload['data']['results'][0]['worker'] == 'backend-dev'
    assert payload['data']['results'][1]['status'] == 'duplicate'
    assert payload['data']['results'][1]['reason'] == '重复任务已跳过'
    assert payload['data']['results'][2]['status'] == 'created'
    assert payload['data']['results'][2]['worker'] == 'docs-writer'


def test_batch_route_creative_cards_returns_structured_validation_error() -> None:
    """批量路由应对非法输入返回结构化错误。

    Returns:
        None.
    """
    response = client.post(
        '/api/v1/creative-cards/batch-route',
        json={'items': []},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload['detail'] == 'List should have at least 1 item after validation, not 0'
    assert payload['error']['code'] == 'validation_error'
    assert payload['error']['message'] == 'Request validation failed'
    assert isinstance(payload['error']['details'], list)


def test_batch_route_creative_cards_handles_unknown_type() -> None:
    """批量路由应返回失败原因。

    Returns:
        None.
    """
    response = client.post(
        '/api/v1/creative-cards/batch-route',
        json={'items': [{'description': '做一个难以识别的创意任务'}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['data']['summary'] == {'total': 1, 'created': 0, 'failed': 1, 'duplicates': 0}
    assert payload['data']['results'][0]['status'] == 'failed'
    assert payload['data']['results'][0]['reason'] == '无法识别任务类型'


def test_creative_task_generator_returns_two_cards() -> None:
    """创意任务生成器应返回两条任务卡片。

    Returns:
        None.
    """
    response = client.get('/api/v1/idle-backend-task-recommender')

    assert response.status_code in {401, 403}
    payload = response.json()
    assert 'detail' in payload
