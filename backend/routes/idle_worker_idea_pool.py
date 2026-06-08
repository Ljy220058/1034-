from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..models import ApiResponse
from ..worker_board import build_worker_board
from .common import CurrentUser, get_current_user

router = APIRouter(prefix='/api/v1/workers', tags=['workers'])

ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    'backend': ('backend', 'fastapi', 'sqlite', 'api', '数据库', '后端'),
    'frontend': ('frontend', 'html', 'css', 'ui', '页面', '前端'),
    'test': ('test', 'pytest', 'qa', '验收', '测试'),
    'review': ('review', 'quality', '安全', '评审', '审查'),
}
VALID_ROLES = set(ROLE_KEYWORDS)
VALID_STATUSES = {'todo', 'ready', 'running', 'blocked'}
DEFAULT_CANDIDATE_STATUSES = {'todo', 'ready'}


def _require_admin_or_leader(current_user: CurrentUser) -> None:
    """校验当前用户是否为管理员或团长。

    Args:
        current_user: 当前登录用户。

    Raises:
        HTTPException: 用户角色无权访问时返回 403。
    """
    if current_user.role not in {'admin', 'leader'}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='仅管理员或团长可查看')


def _normalize_workspace_path(workspace_path: str) -> str:
    """标准化工作区路径。

    Args:
        workspace_path: 请求传入的工作区路径。

    Returns:
        绝对工作区路径。

    Raises:
        HTTPException: 路径为空或不是绝对路径时返回 422。
    """
    cleaned = workspace_path.strip()
    if not cleaned or cleaned.startswith('dir:') or not Path(cleaned).expanduser().is_absolute():
        raise HTTPException(status_code=422, detail='工作区参数不合法')
    return str(Path(cleaned).expanduser().resolve())


def _normalize_role(role: str | None) -> str | None:
    """校验并标准化 worker 角色筛选。"""
    if role is None:
        return None
    normalized = role.strip().lower()
    if normalized not in VALID_ROLES:
        raise HTTPException(status_code=422, detail='worker 角色不合法')
    return normalized


def _normalize_status_filter(raw_status: str | None) -> set[str]:
    """校验并标准化任务状态筛选。"""
    if raw_status is None:
        return set(DEFAULT_CANDIDATE_STATUSES)
    values = {item.strip().lower() for item in raw_status.split(',') if item.strip()}
    if not values or not values.issubset(VALID_STATUSES):
        raise HTTPException(status_code=422, detail='任务状态不合法')
    return values


def _worker_role(worker: dict[str, Any]) -> str:
    """根据 worker 名称和能力推断角色。"""
    text = ' '.join(str(item) for item in [worker.get('worker_key'), worker.get('name'), *(worker.get('capabilities') or [])]).lower()
    for role, keywords in ROLE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return role
    return 'backend'


def _public_worker(worker: dict[str, Any], role: str) -> dict[str, Any]:
    """构造前端可展示的 worker 摘要。"""
    return {
        'worker_key': worker.get('worker_key'),
        'name': worker.get('name'),
        'role': role,
        'status': worker.get('status'),
        'capabilities': list(worker.get('capabilities') or []),
        'last_seen_at': worker.get('last_seen_at'),
    }


def _candidate_card(task: dict[str, Any], worker: dict[str, Any], role: str) -> dict[str, Any]:
    """构造可承接创意卡片候选。"""
    task_key = task.get('task_key') or task.get('task_id')
    worker_key = worker.get('worker_key') or worker.get('name')
    return {
        'task_key': task_key,
        'task_id': task.get('task_id'),
        'title': task.get('title'),
        'status': task.get('status'),
        'priority': int(task.get('priority') or 0),
        'assignee': task.get('assignee'),
        'description': task.get('description', ''),
        'reason': f'推荐给 {worker_key}：该 worker 当前空闲，角色为 {role}，可承接该创意卡片。',
    }


def _build_role_pool(role: str, workers: list[dict[str, Any]], tasks: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    """按角色构建空闲 worker 创意池分组。"""
    primary_worker = workers[0]
    candidates = sorted(
        (_candidate_card(task, primary_worker, role) for task in tasks),
        key=lambda item: (-int(item['priority']), str(item['task_key'])),
    )[:limit]
    return {
        'role': role,
        'workers': [_public_worker(worker, role) for worker in workers],
        'candidate_count': len(candidates),
        'candidates': candidates,
    }


@router.get('/idle-idea-pool', response_model=ApiResponse)
def read_idle_worker_idea_pool(
    current_user: CurrentUser = Depends(get_current_user),
    workspace_path: str = Query(min_length=1, max_length=500),
    role: str | None = Query(default=None, min_length=1, max_length=40),
    status: str | None = Query(default=None, min_length=1, max_length=80),
    limit: int = Query(default=10, ge=1, le=50),
) -> ApiResponse:
    """返回空闲 worker 可承接创意卡片候选池。

    Args:
        current_user: 当前登录用户，仅管理员或团长可访问。
        workspace_path: 工作区绝对路径。
        role: 可选 worker 角色筛选。
        status: 可选任务状态筛选，支持逗号分隔。
        limit: 每个角色最多返回的候选卡片数。

    Returns:
        按 worker 角色聚合的创意卡片候选池。
    """
    _require_admin_or_leader(current_user)
    normalized_workspace = _normalize_workspace_path(workspace_path)
    normalized_role = _normalize_role(role)
    status_filter = _normalize_status_filter(status)
    board = build_worker_board(normalized_workspace)
    idle_by_role: dict[str, list[dict[str, Any]]] = {}
    for worker in board.get('idle_workers', []):
        if not isinstance(worker, dict) or worker.get('status') != 'active':
            continue
        worker_role = _worker_role(worker)
        if normalized_role and worker_role != normalized_role:
            continue
        idle_by_role.setdefault(worker_role, []).append(worker)
    tasks = [
        task
        for task in board.get('recent_changes', [])
        if isinstance(task, dict) and str(task.get('status')) in status_filter and not task.get('assignee')
    ]
    roles = [_build_role_pool(item[0], item[1], tasks, limit) for item in sorted(idle_by_role.items())]
    return ApiResponse(
        data={
            'workspace_path': normalized_workspace,
            'filters': {
                'role': normalized_role,
                'status': sorted(status_filter),
            },
            'summary': {
                'idle_worker_count': sum(len(workers) for workers in idle_by_role.values()),
                'candidate_count': sum(role_item['candidate_count'] for role_item in roles),
                'role_count': len(roles),
            },
            'roles': roles,
        },
        message='已生成空闲 worker 创意池',
    )
