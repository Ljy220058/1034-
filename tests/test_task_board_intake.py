from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app


client = TestClient(app, raise_server_exceptions=False)


def test_task_board_intake_get_returns_default_rules() -> None:
    """任务灵感看板默认规则接口应返回结构化响应。"""
    response = client.get('/api/v1/task-board/intake')

    assert response.status_code == 200
    body = response.json()
    assert body['message'] == '已返回任务灵感看板默认规则'
    assert 'data' in body
    assert body['data']['count'] == 3
    assert len(body['data']['cards']) == 3
    assert body['data']['default_rules'][0].startswith('按模块分类')
    assert body['data']['cards'][0]['title'].startswith('中文创意：')


def test_task_board_intake_post_uses_hints_and_returns_three_cards() -> None:
    """任务灵感看板创建接口应按提示词生成三条卡片。"""
    response = client.post(
        '/api/v1/task-board/intake',
        json={
            'topic': '为 FastAPI 后端设计一个 SQLite 查询汇总接口',
            'module_hint': 'backend',
            'priority_hint': 'P0',
            'delivery_hint': '接口',
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body['message'] == '已生成任务灵感看板'
    assert body['data']['count'] == 3
    cards = body['data']['cards']
    assert len(cards) == 3
    assert all(card['module'] == 'backend' for card in cards)
    assert all(card['priority'] == 'P0' for card in cards)
    assert all(card['delivery_type'] == '接口' for card in cards)
    assert cards[0]['default_fields']['response_format'] == '{"data": ..., "message": "中文"}'
    assert any('FastAPI' in card['description'] for card in cards)
