from __future__ import annotations

import json
from typing import Any

SECTION_KEYS = ('可能原因', '建议动作', '需要人工确认的信息')


def _stringify(value: Any) -> str:
    """Convert task evidence values to compact Chinese-readable text."""
    if value is None:
        return ''
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)


def _first_text(*values: Any) -> str:
    for value in values:
        text = _stringify(value)
        if text:
            return text
    return ''


def _collect_comments(task: dict[str, Any]) -> list[str]:
    comments = task.get('comments') or []
    result: list[str] = []
    if not isinstance(comments, list):
        return result
    for comment in comments[:5]:
        if isinstance(comment, dict):
            text = _first_text(comment.get('body'), comment.get('comment'), comment.get('text'), comment.get('message'))
        else:
            text = _stringify(comment)
        if text:
            result.append(text)
    return result


def _collect_recent_events(task: dict[str, Any]) -> list[str]:
    events = task.get('recent_events') or task.get('events') or []
    result: list[str] = []
    if not isinstance(events, list):
        return result
    for event in events[-5:]:
        if isinstance(event, dict):
            kind = _stringify(event.get('kind') or event.get('type') or event.get('event'))
            payload = event.get('payload')
            payload_text = _stringify(payload)
            text = f'{kind}: {payload_text}' if kind and payload_text else kind or payload_text
        else:
            text = _stringify(event)
        if text:
            result.append(text)
    return result


def _find_block_reason(task: dict[str, Any], comments: list[str], events: list[str]) -> str:
    reason = _first_text(
        task.get('block_reason'),
        task.get('blocked_reason'),
        task.get('last_failure_reason'),
        task.get('failure_reason'),
        task.get('result'),
    )
    if reason:
        return reason
    for event in reversed(events):
        if any(token in event.lower() for token in ('blocked', 'block', 'failed', 'failure', 'error', 'spawn_failed')):
            return event
    return comments[-1] if comments else ''


def _manual_confirmation_text(reason: str, status: str, comments: list[str]) -> str:
    combined = ' '.join([reason, *comments]).strip()
    if status == 'todo':
        return '暂无必须人工确认的信息；如验收标准不清，再补充评论说明。'
    if any(token in combined for token in ('确认', '人工', '是否', '选择', '凭证', '权限', '账号', '密钥', 'token', 'API key')):
        return combined
    if status == 'triage':
        return '确认重建后应分配给哪类新人 worker；若无明确偏好，按原 assignee 或当前空闲 worker 继续。'
    return '确认是否存在外部凭证、权限或产品取舍；如果没有，执行者应自行修复并继续推进。'


def build_blocked_task_advice(task: dict[str, Any]) -> dict[str, Any]:
    """Build Chinese self-unblock advice from reusable task state fields.

    The input intentionally accepts plain dictionaries so it can be used by
    backend routes, CLI scripts, or frontend-provided board snapshots.
    """
    task_id = _first_text(task.get('task_id'), task.get('id'), task.get('task_key'))
    title = _first_text(task.get('title')) or '未命名任务'
    status = _first_text(task.get('status')).lower() or 'unknown'
    assignee = _first_text(task.get('assignee')) or '未指定负责人'
    workspace = _first_text(task.get('workspace'), task.get('workspace_path')) or '未记录工作区'
    comments = _collect_comments(task)
    recent_events = _collect_recent_events(task)
    reason = _find_block_reason(task, comments, recent_events)

    if status == 'blocked':
        possible_reason = reason or '任务被执行者标记为 blocked，可能卡在错误修复、缺少上下文或等待确认。'
        suggested_action = (
            f'负责人 {assignee} 在工作区 {workspace} 继续处理：先复现最近失败，阅读评论与最近事件，'
            '能自行修复就直接修；若只是等待确认，补齐假设后继续推进，不要停在 blocked。'
        )
    elif status == 'triage':
        possible_reason = reason or '连续失败或系统自动分拣，任务需要从失败状态恢复。'
        if '连续失败或系统自动分拣' not in possible_reason:
            possible_reason = f'连续失败或系统自动分拣；最近线索：{possible_reason}'
        suggested_action = (
            f'对原任务执行 archive + recreate，并分配给 {assignee} 或当前更空闲/更匹配的 worker；'
            f'重建任务时保留标题「{title}」、工作区 {workspace}、最近失败线索和验收标准。'
        )
    else:
        possible_reason = f'当前未处于 blocked/triage，状态为 {status}，通常不需要自助解锁。'
        suggested_action = f'保持队列流转：由 {assignee} 按正常优先级继续处理；工作区为 {workspace}。'

    sections = {
        '可能原因': possible_reason,
        '建议动作': suggested_action,
        '需要人工确认的信息': _manual_confirmation_text(reason, status, comments),
    }
    return {
        'language': 'zh-CN',
        'task_id': task_id,
        'title': title,
        'status': status,
        'assignee': assignee,
        'workspace': workspace,
        'sections': sections,
        'evidence': {
            'block_reason': reason,
            'comments': comments,
            'recent_events': recent_events,
        },
    }


def build_blocked_task_advice_examples() -> list[dict[str, Any]]:
    """Return lightweight example data covering blocked, triage, and todo."""
    examples = [
        {
            'task_id': 't_blocked_example',
            'title': '接口测试失败等待处理',
            'status': 'blocked',
            'assignee': 'backend-dev',
            'workspace': '/workspace/project',
            'block_reason': 'pytest 失败，提示数据库字段缺失。',
            'comments': [{'body': '最近一次失败发生在 tests/test_api.py。'}],
            'recent_events': [{'kind': 'blocked', 'payload': {'reason': '数据库字段缺失'}}],
        },
        {
            'task_id': 't_triage_example',
            'title': '前端页面多次重试失败',
            'status': 'triage',
            'assignee': 'frontend-dev',
            'workspace': '/workspace/project',
            'comments': [{'body': '连续失败，最后一次是构建超时。'}],
            'recent_events': [{'kind': 'spawn_failed', 'payload': {'error': 'build timeout'}}],
        },
        {
            'task_id': 't_todo_example',
            'title': '补充说明文档',
            'status': 'todo',
            'assignee': 'writer',
            'workspace': '/workspace/project',
            'comments': [],
            'recent_events': [{'kind': 'created', 'payload': {'assignee': 'writer'}}],
        },
    ]
    return [build_blocked_task_advice(example) for example in examples]
