from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..models import ApiResponse
from ..repository import list_workspace_task_items as repository_list_workspace_task_items
from ..worker_board import build_worker_board
from ..worker_recommendations import list_queue_workers
from .common import CurrentUser, admin_or_leader, get_current_user

router = APIRouter(prefix='/api/v1', tags=['task-priority-routing'])

DEFAULT_WORKSPACE_PATH = '/root/autodl-tmp/projects/hermes-swarm-lab'
ACTIVE_TASK_STATUSES = {'todo', 'ready', 'running', 'blocked'}
TASK_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    'backend': ('后端', 'api', 'fastapi', 'sqlite', '数据库', 'backend', 'server'),
    'frontend': ('前端', '页面', 'ui', 'html', 'css', 'react', 'vue', 'frontend'),
    'test': ('测试', 'pytest', '回归', '验证', 'test', 'qa'),
    'review': ('评审', '审查', 'review', '安全', 'security'),
    'qa': ('验收', '联调', '手测', '冒烟', '检查'),
}


class PriorityRouteRequest(BaseModel):
    """Priority routing request payload.

    Attributes:
        task_key: Stable task key.
        title: Task title.
        description: Optional task description.
        priority: Task priority used as a tie breaker.
        workspace_path: Workspace path for reading current board load.
    """

    task_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=2000)
    priority: int = Field(default=0, ge=0, le=999)
    workspace_path: str = Field(min_length=1, max_length=500)


class TaskBoardSidebarRequest(BaseModel):
    """Task board sidebar request payload.

    Attributes:
        workspace_path: Workspace path used to inspect tasks.
        status: Optional status filter.
        limit: Maximum tasks to return.
    """

    workspace_path: str = Field(default=DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500)
    status: str | None = Field(default=None, max_length=20)
    limit: int = Field(default=20, ge=1, le=200)


class TaskBoardSidebarItem(BaseModel):
    """Task sidebar item payload.

    Attributes:
        task_key: Stable task key.
        title: Task title.
        assignee: Task assignee.
        status: Current task status.
        updated_at: Latest update time.
        priority: Priority value.
        workspace: Workspace path.
        description: Task description.
    """

    task_key: str
    title: str
    assignee: str | None
    status: str
    updated_at: str
    priority: int
    workspace: str
    description: str = ''


class TaskBoardSidebarResponse(BaseModel):
    """Task board sidebar response payload.

    Attributes:
        workspace_path: Workspace path used for the snapshot.
        status_filter: Active status filter.
        summary: Status counts.
        tasks: Sidebar tasks.
        updated_at: Snapshot time.
    """

    workspace_path: str
    status_filter: str | None
    summary: dict[str, int]
    tasks: list[TaskBoardSidebarItem]
    updated_at: str


class TaskBoardDispatchRequest(BaseModel):
    """Task board dispatch request payload."""

    task_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=2000)
    workspace_path: str = Field(default=DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500)
    limit: int = Field(default=20, ge=1, le=200)


def _normalize_workspace_path(workspace_path: str) -> str:
    """Normalize a workspace path for repository lookups."""
    normalized = str(workspace_path).strip()
    return normalized or DEFAULT_WORKSPACE_PATH


class TaskBoardIntakeCard(BaseModel):
    """Task board intake card payload."""

    title: str
    description: str
    default_fields: dict[str, str]


def _as_dict(value: Any) -> dict[str, Any]:
    """Convert a repository result to a plain dict when possible."""
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, 'model_dump', None)
    if callable(model_dump):
        dumped = model_dump(mode='json')
        return dict(dumped) if isinstance(dumped, dict) else {'value': dumped}
    if hasattr(value, '__dict__'):
        return dict(value.__dict__)
    try:
        return dict(value)
    except Exception:
        return {'value': value}


def _task_type_from_text(title: str, description: str) -> tuple[str, list[str]]:
    """Infer a task type from title and description.

    Args:
        title: Task title.
        description: Task description.

    Returns:
        Inferred task type and human-readable decision reasons.
    """
    content = f"{title}\n{description}".lower()
    scores: dict[str, int] = {task_type: 0 for task_type in TASK_TYPE_KEYWORDS}
    reasons: list[str] = []
    for task_type, keywords in TASK_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in content:
                scores[task_type] += 1
                reasons.append(f'任务内容命中「{keyword}」，倾向 {task_type}')
    best_type, best_score = max(scores.items(), key=lambda item: (item[1], item[0]))
    if best_score == 0:
        return 'backend', ['未命中明确任务类型，默认按 backend 分配']
    return best_type, reasons


def _worker_matches_type(worker: dict[str, Any], task_type: str) -> tuple[bool, list[str]]:
    """Check whether a worker matches the inferred task type.

    Args:
        worker: Worker row.
        task_type: Inferred task type.

    Returns:
        Match flag and scoring reasons.
    """
    keywords = TASK_TYPE_KEYWORDS.get(task_type, ())
    capability_text = ' '.join([str(worker.get('worker_key', '')), str(worker.get('name', '')), *[str(item) for item in worker.get('capabilities', [])]]).lower()
    matched = [keyword for keyword in keywords if keyword.lower() in capability_text]
    if not matched:
        return False, ['能力未命中任务类型，作为兜底候选']
    return True, [f'能力命中 {", ".join(matched[:4])}']


def _running_load_by_worker(tasks: list[dict[str, Any]]) -> dict[str, int]:
    """Count running tasks by assignee."""
    loads: dict[str, int] = {}
    for task in tasks:
        if str(task.get('status')) in {'running', 'doing'} and task.get('assignee'):
            assignee = str(task['assignee'])
            loads[assignee] = loads.get(assignee, 0) + 1
    return loads


def _task_counts(tasks: list[dict[str, Any]]) -> dict[str, int]:
    """Count board tasks by status group."""
    return {
        'total_tasks': len(tasks),
        'running_tasks': sum(1 for task in tasks if str(task.get('status')) in {'running', 'doing'}),
        'dispatchable_tasks': sum(1 for task in tasks if str(task.get('status')) in {'todo', 'ready'}),
        'blocked_tasks': sum(1 for task in tasks if str(task.get('status')) == 'blocked'),
    }


def _rank_workers(
    *,
    task_type: str,
    title: str,
    preferred_worker: str | None,
    workers: list[dict[str, Any]],
    load_map: dict[str, int],
) -> list[dict[str, Any]]:
    """Rank workers for a task."""
    candidates: list[dict[str, Any]] = []
    for worker in workers:
        matched, match_reasons = _worker_matches_type(worker, task_type)
        worker_key = str(worker.get('worker_key', ''))
        running_load = load_map.get(worker_key, load_map.get(str(worker.get('name', '')), 0))
        score = (100 if matched else 20) - running_load * 10
        reasons = match_reasons + [f'当前运行任务数 {running_load}']
        if preferred_worker and worker_key == preferred_worker:
            score += 20
            reasons.append('命中用户指定的 preferred_worker')
        if task_type == 'backend' and any(token in f"{worker_key} {worker.get('name', '')} {' '.join([str(item) for item in worker.get('capabilities', [])])}".lower() for token in ('api', 'db', 'sqlite', 'fastapi', 'server', 'backend')):
            score += 10
            reasons.append('偏后端能力匹配')
        candidates.append(
            {
                'worker_key': worker_key,
                'name': worker.get('name'),
                'status': worker.get('status'),
                'capabilities': worker.get('capabilities', []),
                'score': score,
                'load': {'running_tasks': running_load},
                'reasons': reasons,
            }
        )
    candidates.sort(key=lambda item: (-int(item['score']), int(item['load']['running_tasks']), str(item['worker_key'])))
    return candidates


@router.get('/task-board/intake', response_model=ApiResponse)
def read_task_board_intake() -> ApiResponse:
    """返回任务灵感看板的默认规则说明。"""
    return ApiResponse(
        data={
            'count': 3,
            'cards': [
                {
                    'title': '中文创意：后端看板路由提示',
                    'description': '自动识别新任务的标签、优先级与当前负载，给空闲后端 worker 生成可执行提示。',
                    'default_fields': {
                        'module': 'backend',
                        'priority': 'P1',
                        'delivery_type': '路由提示',
                        'response_format': '{"data": ..., "message": "中文"}',
                        'error_format': '{"detail": "中文描述"}',
                    },
                },
                {
                    'title': '中文创意：测试优先级分流',
                    'description': '当任务包含测试、验证或回归时，优先推荐空闲测试 worker 并说明原因。',
                    'default_fields': {
                        'module': 'test',
                        'priority': 'P1',
                        'delivery_type': '路由提示',
                        'response_format': '{"data": ..., "message": "中文"}',
                        'error_format': '{"detail": "中文描述"}',
                    },
                },
                {
                    'title': '中文创意：评审兜底分流',
                    'description': '当无法明确判断任务类型时，返回结构化评审建议与当前负载信息。',
                    'default_fields': {
                        'module': 'review',
                        'priority': 'P2',
                        'delivery_type': '路由提示',
                        'response_format': '{"data": ..., "message": "中文"}',
                        'error_format': '{"detail": "中文描述"}',
                    },
                },
            ],
        },
        message='已返回任务灵感看板默认规则',
    )


@router.post('/task-board/route', response_model=ApiResponse)
def route_task_board(payload: TaskBoardDispatchRequest) -> ApiResponse:
    """Generate lightweight routing hints for new board tasks."""
    normalized_workspace = _normalize_workspace_path(payload.workspace_path)
    board = _as_dict(build_worker_board(normalized_workspace))
    raw_workers = []
    for key in ('idle_workers', 'busy_workers', 'workers', 'active_workers'):
        value = board.get(key, [])
        if isinstance(value, list):
            raw_workers.extend(value)
    active_workers = [worker for worker in raw_workers if isinstance(worker, dict) and str(worker.get('status')) == 'active']
    if not active_workers:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='暂无可分配的 active worker')

    tasks = repository_list_workspace_task_items(normalized_workspace, limit=payload.limit)
    task_dicts = [_as_dict(task) for task in tasks]
    task_type, task_reasons = _task_type_from_text(payload.title, payload.description)
    load_map = _running_load_by_worker(task_dicts)
    candidates = _rank_workers(
        task_type=task_type,
        title=payload.title,
        preferred_worker=None,
        workers=active_workers,
        load_map=load_map,
    )
    selected = candidates[0]
    return ApiResponse(
        data={
            'workspace_path': normalized_workspace,
            'task_key': payload.task_key,
            'title': payload.title.strip(),
            'task_type': task_type,
            'task_type_reasons': task_reasons,
            'selected_worker': selected,
            'candidates': candidates[:5],
            'board_summary': _task_counts(task_dicts),
            'updated_at': datetime.now(timezone.utc).isoformat(),
        },
        message='已生成任务看板路由建议',
    )


@router.get('/task-board/sidebar', response_model=ApiResponse)
def read_task_board_sidebar(
    workspace_path: str = Query(default=DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500),
    status_filter: str | None = Query(default=None, alias='status', min_length=1, max_length=20),
    limit: int = Query(default=20, ge=1, le=200),
) -> ApiResponse:
    """返回任务可视化侧栏。"""
    normalized_workspace = _normalize_workspace_path(workspace_path)
    recent_tasks = [_as_dict(task) for task in repository_list_workspace_task_items(normalized_workspace, limit=limit)]
    allowed_statuses = {'todo', 'ready', 'running', 'blocked', 'done', 'archived'}
    normalized_status = str(status_filter).strip().lower() if status_filter else ''
    if normalized_status and normalized_status not in allowed_statuses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='状态筛选参数无效')

    filtered_tasks = [task for task in recent_tasks if not normalized_status or str(task.get('status') or '').lower() == normalized_status]
    tasks = [
        TaskBoardSidebarItem(
            task_key=str(task.get('task_key') or ''),
            title=str(task.get('title') or ''),
            assignee=task.get('assignee'),
            status=str(task.get('status') or 'unknown'),
            updated_at=str(task.get('updated_at') or ''),
            priority=int(task.get('priority') or 0),
            workspace=str(task.get('workspace') or normalized_workspace),
            description=str(task.get('description') or ''),
        )
        for task in filtered_tasks
    ]
    summary = {
        'total': len(recent_tasks),
        'todo': sum(1 for task in recent_tasks if str(task.get('status') or '').lower() == 'todo'),
        'ready': sum(1 for task in recent_tasks if str(task.get('status') or '').lower() == 'ready'),
        'running': sum(1 for task in recent_tasks if str(task.get('status') or '').lower() in {'running', 'doing'}),
        'blocked': sum(1 for task in recent_tasks if str(task.get('status') or '').lower() == 'blocked'),
        'done': sum(1 for task in recent_tasks if str(task.get('status') or '').lower() == 'done'),
        'archived': sum(1 for task in recent_tasks if str(task.get('status') or '').lower() == 'archived'),
    }
    message = '已返回任务侧栏'
    if normalized_status:
        message = f'已返回 {normalized_status} 任务侧栏'
    return ApiResponse(
        data=TaskBoardSidebarResponse(
            workspace_path=normalized_workspace,
            status_filter=normalized_status or None,
            summary=summary,
            tasks=tasks,
            updated_at=datetime.now(timezone.utc).isoformat(),
        ).model_dump(mode='json'),
        message=message,
    )
