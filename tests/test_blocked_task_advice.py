from __future__ import annotations

from pathlib import Path

from backend.blocked_task_advice import build_blocked_task_advice, build_blocked_task_advice_examples


def test_build_blocked_task_advice_covers_blocked_triage_and_todo() -> None:
    blocked = build_blocked_task_advice({
        'task_id': 't_blocked',
        'title': '接口测试失败等待处理',
        'status': 'blocked',
        'assignee': 'backend-dev',
        'workspace': '/workspace/project',
        'block_reason': 'pytest 失败，提示数据库字段缺失。',
        'comments': [{'body': '最近一次失败发生在 tests/test_api.py。'}],
        'recent_events': [{'kind': 'blocked', 'payload': {'reason': '数据库字段缺失'}}],
    })
    triage = build_blocked_task_advice({
        'task_id': 't_triage',
        'title': '前端页面多次重试失败',
        'status': 'triage',
        'assignee': 'frontend-dev',
        'workspace': '/workspace/project',
        'comments': [{'body': '连续失败，最后一次是构建超时。'}],
        'recent_events': [{'kind': 'spawn_failed', 'payload': {'error': 'build timeout'}}],
    })
    todo = build_blocked_task_advice({
        'task_id': 't_todo',
        'title': '补充说明文档',
        'status': 'todo',
        'assignee': 'writer',
        'workspace': '/workspace/project',
    })

    assert blocked['status'] == 'blocked'
    assert blocked['sections']['可能原因'].startswith('pytest 失败')
    assert '继续处理' in blocked['sections']['建议动作']
    assert triage['status'] == 'triage'
    assert 'archive + recreate' in triage['sections']['建议动作']
    assert todo['status'] == 'todo'
    assert '暂无必须人工确认的信息' in todo['sections']['需要人工确认的信息']


def test_blocked_task_advice_examples_cover_three_scenarios() -> None:
    examples = build_blocked_task_advice_examples()

    assert len(examples) == 3
    assert {item['status'] for item in examples} == {'blocked', 'triage', 'todo'}

