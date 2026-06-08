from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .task_board_models import list_workspace_tasks


@dataclass(frozen=True)
class DiagnosticTaskInput:
    """Normalized task input for non-mutating unblock diagnostics."""

    task_id: str
    title: str
    description: str
    status: str
    assignee: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    recent_results: list[str] = field(default_factory=list)
    health: dict[str, Any] | None = None


def _as_text(value: Any) -> str:
    """Convert a value to compact text for keyword checks."""
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return str(value)


def _recent_results_from_metadata(metadata: dict[str, Any]) -> list[str]:
    raw = metadata.get('recent_results') or metadata.get('recent_failures') or metadata.get('results') or []
    if isinstance(raw, list):
        return [_as_text(item) for item in raw if _as_text(item).strip()]
    text = _as_text(raw).strip()
    return [text] if text else []


def _normalize_task(task: dict[str, Any] | DiagnosticTaskInput) -> DiagnosticTaskInput:
    if isinstance(task, DiagnosticTaskInput):
        return task
    metadata = task.get('metadata') if isinstance(task.get('metadata'), dict) else {}
    health = task.get('health') if isinstance(task.get('health'), dict) else None
    recent_results = task.get('recent_results')
    if not isinstance(recent_results, list):
        recent_results = _recent_results_from_metadata(metadata)
    return DiagnosticTaskInput(
        task_id=_as_text(task.get('task_id') or task.get('task_key') or 'unknown'),
        title=_as_text(task.get('title')),
        description=_as_text(task.get('description') or metadata.get('description') or metadata.get('summary')),
        status=_as_text(task.get('status') or 'todo').lower(),
        assignee=_as_text(task.get('assignee')).strip() or None,
        metadata=metadata,
        recent_results=[_as_text(item) for item in recent_results if _as_text(item).strip()],
        health=health,
    )


def _recommended_assignee(task: DiagnosticTaskInput) -> tuple[str, str]:
    explicit = task.metadata.get('suggested_assignee') or task.metadata.get('suggested_role')
    if explicit:
        return _as_text(explicit), '任务元数据已提供建议负责人'
    haystack = f'{task.title} {task.description} {" ".join(task.recent_results)}'.lower()
    keyword_roles = [
        (('安全', 'security', 'auth', 'token', '权限', '注入'), 'security-reviewer', '涉及安全、权限或认证风险'),
        (('前端', 'frontend', 'ui', '页面', '交互', 'react'), 'frontend-dev', '涉及前端页面或交互'),
        (('后端', 'backend', 'api', '接口', '数据库', 'sqlite', 'fastapi'), 'backend-dev', '涉及后端接口或数据持久化'),
        (('测试', 'pytest', '失败', '回归', '验收'), 'qa-tester', '主要阻塞点是测试或验收失败'),
        (('文案', '创意', '内容', '海报'), 'creative-worker', '涉及内容或创意产出'),
    ]
    for keywords, role, reason in keyword_roles:
        if any(keyword in haystack for keyword in keywords):
            return role, reason
    if task.assignee:
        return task.assignee, '保留当前负责人继续排障'
    return 'unblocker', '缺少明确领域线索，先交给 unblocker 补齐上下文'


def _status_guidance(task: DiagnosticTaskInput) -> tuple[str, list[str], list[str], str]:
    last_failure = ''
    if task.health:
        last_failure = _as_text(task.health.get('last_failure_reason'))
    if not last_failure and task.recent_results:
        last_failure = task.recent_results[0]

    if task.status == 'blocked':
        summary = f'任务处于 blocked，需要根据最近失败信息定位卡点。最近结果：{last_failure or "未记录"}'
        missing = ['阻塞原因的原始错误日志或命令输出', '已尝试过的修复方案', '期望验收标准和失败截图/报错']
        actions = ['先复现最近一次失败', '按错误类型自行补齐缺失输入，不等待人工确认', '修复后运行最小验证并记录结果']
        next_step = '解除等待状态前，优先补齐错误日志并让推荐负责人继续排障。'
    elif task.status == 'triage':
        summary = '任务处于 triage，通常表示多次失败或规格不完整，需要重建为可执行任务。'
        missing = ['失败次数和失败模式', '原任务的最小可交付范围', '应该接手的新角色和明确验收标准']
        actions = ['整理失败摘要', '拆成单一目标的新任务', '分配给更匹配的新人或资深排障角色']
        next_step = '归档原 triage 记录并用清晰规格重建任务，但本诊断器只输出建议不改状态。'
    else:
        summary = '任务尚未进入阻塞态，重点是提前补齐执行信息，避免后续卡住。'
        missing = ['输入样例或数据来源', '完成定义', '预期负责人和优先级']
        actions = ['确认任务是否可直接执行', '若 assignee 为空则分配空闲且能力匹配的 worker', '要求执行者先跑最小示例']
        next_step = '补齐最小输入后派发执行；如果发现真实阻塞，再升级为 blocked 诊断。'
    return summary, missing, actions, next_step


def _self_recovery_guides(task: DiagnosticTaskInput) -> list[dict[str, str]]:
    """Return Chinese self-recovery prompts for common blocked-task causes."""
    task_ref = task.task_id or '<任务ID>'
    return [
        {
            'category': '缺少上下文',
            'title': '缺少上下文：先从任务详情和评论补齐输入',
            'phenomenon': '现象：任务描述、验收标准、输入样例或历史评论不足，worker 不知道从哪里开始复现。',
            'recommended_action': '建议操作：打开任务详情，阅读正文、评论、父任务交付和最近运行记录；把缺失信息整理成最小可执行假设后继续推进，不等待人工确认。',
            'copyable_command_or_entry': f'入口：hermes kanban show {task_ref}',
        },
        {
            'category': '测试失败',
            'title': '测试失败：先复现最小失败用例',
            'phenomenon': '现象：pytest、构建、lint 或验收脚本失败，最近结果中出现失败断言、Traceback 或非零退出码。',
            'recommended_action': '建议操作：只运行失败的最小测试或脚本，确认失败原因后按 RED-GREEN 方式修复；通过后再扩大到相关测试集。',
            'copyable_command_or_entry': "命令：python -m pytest <失败测试路径或节点> -q -o 'addopts='",
        },
        {
            'category': '权限问题',
            'title': '权限问题：确认角色、令牌和工作区访问范围',
            'phenomenon': '现象：接口返回 401/403，命令提示 permission denied，或工作区路径/文件访问被拒绝。',
            'recommended_action': '建议操作：检查当前调用是否带有有效 Authorization、账号是否具备 leader/admin 权限，以及路径是否仍在允许工作区内；能用测试令牌复现时优先补自动化验证。',
            'copyable_command_or_entry': "命令：curl -i -H 'Authorization: Bearer ***' http://localhost:8000/api/v1/workspaces/tasks/diagnostics?workspace_path=.",
        },
        {
            'category': '依赖任务未完成',
            'title': '依赖任务未完成：检查父任务和上游交付',
            'phenomenon': '现象：任务依赖父任务、上游接口、数据文件或评审结果，但相关交付尚未完成或未写清输出路径。',
            'recommended_action': '建议操作：先检查父任务状态和交付摘要；若父任务未完成，不要强行解封，等待调度器正常按依赖推进；若只是缺少路径说明，按已有产物推断并记录假设。',
            'copyable_command_or_entry': f'入口：hermes kanban show {task_ref}  # 查看 Parents / parent handoffs',
        },
    ]


def build_task_diagnostic_suggestion(task: dict[str, Any] | DiagnosticTaskInput) -> dict[str, Any]:
    """Build a structured Chinese diagnostic suggestion without mutating task state."""
    normalized = _normalize_task(task)
    recommended_assignee, assignee_reason = _recommended_assignee(normalized)
    problem_summary, missing_information, action_suggestions, next_step = _status_guidance(normalized)
    return {
        'task_id': normalized.task_id,
        'status': normalized.status,
        'problem_summary': problem_summary,
        'recommended_assignee': recommended_assignee,
        'assignee_reason': assignee_reason,
        'missing_information': missing_information,
        'action_suggestions': action_suggestions,
        'next_step': next_step,
        'self_recovery_guides': _self_recovery_guides(normalized),
        'recent_results_used': normalized.recent_results[:3],
        'non_mutating': True,
    }


def build_workspace_task_diagnostics(workspace_path: str | Path, *, limit: int = 100, status_filter: str | None = None) -> dict[str, Any]:
    """Build diagnostics for workspace board tasks without modifying any task state."""
    tasks = list_workspace_tasks(workspace_path, limit=limit, status_filter=status_filter)
    suggestions = [build_task_diagnostic_suggestion(task.model_dump(mode='json')) for task in tasks]
    return {
        'workspace_path': str(Path(workspace_path).expanduser().resolve()),
        'source': 'workspace_task_items_snapshot',
        'summary': {
            'diagnostic_count': len(suggestions),
            'blocked_count': sum(1 for item in suggestions if item['status'] == 'blocked'),
            'triage_count': sum(1 for item in suggestions if item['status'] == 'triage'),
            'todo_count': sum(1 for item in suggestions if item['status'] == 'todo'),
        },
        'diagnostics': suggestions,
        'non_mutating': True,
    }
