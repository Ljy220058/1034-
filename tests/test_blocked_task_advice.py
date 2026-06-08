from __future__ import annotations

from backend.blocked_task_advice import build_blocked_task_advice, build_blocked_task_advice_examples


def test_blocked_task_advice_uses_explicit_block_reason_and_comments() -> None:
    """阻塞任务建议应优先使用显式阻塞原因和评论证据。"""
    advice = build_blocked_task_advice(
        {
            'id': 't_blocked_api',
            'title': '接口返回 500',
            'status': 'blocked',
            'assignee': 'backend-dev',
            'workspace_path': '/workspace/backend',
            'block_reason': 'pytest 失败，活动摘要接口返回 500。',
            'comments': [{'body': '最近失败用例是 tests/test_activity_digest.py。'}],
            'events': [{'kind': 'blocked', 'payload': {'reason': '活动摘要接口返回 500'}}],
        }
    )

    assert advice['language'] == 'zh-CN'
    assert advice['task_id'] == 't_blocked_api'
    assert advice['status'] == 'blocked'
    assert advice['sections']['可能原因'] == 'pytest 失败，活动摘要接口返回 500。'
    assert 'backend-dev' in advice['sections']['建议动作']
    assert '/workspace/backend' in advice['sections']['建议动作']
    assert advice['evidence']['comments'] == ['最近失败用例是 tests/test_activity_digest.py。']


def test_triage_task_advice_preserves_recent_failure_context() -> None:
    """分拣任务建议应保留最近失败线索，便于重建任务。"""
    advice = build_blocked_task_advice(
        {
            'task_key': 't_triage_api',
            'title': '导入向导反复失败',
            'status': 'triage',
            'assignee': 'qa-tester',
            'workspace': '/workspace/imports',
            'recent_events': [
                {'kind': 'spawn_failed', 'payload': {'error': '测试环境缺少依赖'}},
            ],
        }
    )

    assert advice['task_id'] == 't_triage_api'
    assert advice['status'] == 'triage'
    assert advice['assignee'] == 'qa-tester'
    assert advice['sections']['可能原因'].startswith('连续失败或系统自动分拣')
    assert '导入向导反复失败' in advice['sections']['建议动作']
    assert advice['evidence']['recent_events'] == ['spawn_failed: {"error": "测试环境缺少依赖"}']


def test_todo_task_advice_returns_non_blocking_guidance() -> None:
    """未阻塞任务应返回正常流转建议，而不是要求人工处理。"""
    advice = build_blocked_task_advice(
        {
            'id': 't_todo_docs',
            'title': '补充说明文档',
            'status': 'todo',
            'assignee': 'docs-writer',
            'comments': ['验收标准：补充一个 Markdown 示例。'],
        }
    )

    assert advice['status'] == 'todo'
    assert advice['workspace'] == '未记录工作区'
    assert advice['sections']['可能原因'] == '当前未处于 blocked/triage，状态为 todo，通常不需要自助解锁。'
    assert advice['sections']['需要人工确认的信息'] == '暂无必须人工确认的信息；如验收标准不清，再补充评论说明。'


def test_blocked_task_advice_examples_cover_expected_statuses() -> None:
    """内置示例应覆盖 blocked、triage、todo 三类状态。"""
    examples = build_blocked_task_advice_examples()

    assert [example['status'] for example in examples] == ['blocked', 'triage', 'todo']
    assert all(set(example['sections']) == {'可能原因', '建议动作', '需要人工确认的信息'} for example in examples)
    assert all(example['language'] == 'zh-CN' for example in examples)
