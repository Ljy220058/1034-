from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status

from ..models import ApiResponse, TaskItemCreate
from ..repository import list_workspace_task_items, upsert_workspace_task_item
from .common import CurrentUser, admin_or_leader, get_current_user

router = APIRouter(prefix='/api/v1/workspaces', tags=['workspaces'])

VALID_TASK_STATUSES = {'todo', 'ready', 'running', 'blocked', 'done', 'archived'}
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class WorkspaceSummary:
    """Workspace summary payload for board preview.

    Attributes:
        workspace_path: Resolved workspace root path.
        summary: Count summary for task states.
        assignee_distribution: Per-assignee task counts.
        recent_tasks: Recent task rows sorted by updated time.
        non_mutating: Whether the endpoint is read-only.
    """

    workspace_path: str
    summary: dict[str, int]
    assignee_distribution: dict[str, int]
    recent_tasks: list[dict[str, Any]]
    non_mutating: bool = True

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        """Serialize the summary into JSON-ready output.

        Args:
            mode: Serialization mode kept for compatibility.

        Returns:
            JSON-ready workspace summary dictionary.
        """
        return {
            'workspace_path': self.workspace_path,
            'summary': self.summary,
            'assignee_distribution': self.assignee_distribution,
            'recent_tasks': self.recent_tasks,
            'non_mutating': self.non_mutating,
        }


def _resolve_workspace_selector(selector: str | None) -> str:
    """Resolve a workspace selector into a path.

    Args:
        selector: Query selector value.

    Returns:
        Workspace path string.

    Raises:
        HTTPException: If the selector is invalid.
    """
    if selector is None or selector == 'current':
        return str(Path.cwd())
    if selector.startswith('workspace:'):
        return selector.removeprefix('workspace:')
    raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail='工作区选择器不合法')


def _normalize_workspace_path(workspace_path: str) -> str:
    """Normalize and validate a workspace path.

    Args:
        workspace_path: Raw workspace path.

    Returns:
        Absolute workspace path.

    Raises:
        HTTPException: If the path is invalid or outside allowed roots.
    """
    path = Path(workspace_path).expanduser()
    try:
        normalized = path.resolve(strict=False)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail='工作区路径不合法') from exc

    if not normalized.is_relative_to(PROJECT_ROOT) and not normalized.is_relative_to(Path.cwd().resolve()):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail='无权访问该工作区')
    return str(normalized)


def _summarize_workspace_tasks(tasks: list[dict[str, Any]]) -> WorkspaceSummary:
    """Build a board preview summary from workspace tasks.

    Args:
        tasks: Workspace task rows.

    Returns:
        Aggregated workspace summary.
    """
    summary = {key: 0 for key in VALID_TASK_STATUSES}
    assignee_distribution: dict[str, int] = {}
    recent_tasks = sorted(tasks, key=lambda item: item.get('updated_at', ''), reverse=True)[:10]
    for task in tasks:
        status = str(task.get('status', ''))
        if status in summary:
            summary[status] += 1
        assignee = str(task.get('assignee') or '未分配')
        assignee_distribution[assignee] = assignee_distribution.get(assignee, 0) + 1
    return WorkspaceSummary(
        workspace_path='',
        summary={
            'total_tasks': len(tasks),
            'idle_tasks': summary['todo'] + summary['ready'],
            'running_tasks': summary['running'],
            'blocked_tasks': summary['blocked'],
            'completed_tasks': summary['done'],
            'archived_tasks': summary['archived'],
        },
        assignee_distribution=assignee_distribution,
        recent_tasks=recent_tasks,
    )


@router.get('/tasks', response_model=ApiResponse)
def read_workspace_tasks(
    current_user: CurrentUser = Depends(get_current_user),
    workspace: str | None = Query(default=None, min_length=1, max_length=120),
    workspace_path: str | None = Query(default=None, min_length=1, max_length=500),
    status: str | None = Query(default=None, min_length=1, max_length=40),
    limit: int | None = Query(default=None, ge=1, le=100),
) -> ApiResponse:
    """Read workspace tasks for the board view.

    Args:
        current_user: Authenticated user.
        workspace: Optional workspace selector.
        workspace_path: Optional explicit workspace path.
        status: Optional task status filter.
        limit: Maximum number of tasks to return.

    Returns:
        Structured API response with workspace tasks.

    Raises:
        HTTPException: If the user lacks permission or query params are invalid.
    """
    admin_or_leader(current_user)
    selector = workspace_path or workspace
    if status is not None and status not in VALID_TASK_STATUSES:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail='任务状态筛选参数不合法')
    if workspace_path is None and selector is not None and selector not in {'current'} and not selector.startswith('workspace:'):
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail='工作区选择器不合法')
    effective_workspace = _normalize_workspace_path(workspace_path or _resolve_workspace_selector(selector))
    tasks = list_workspace_task_items(effective_workspace, limit=limit or 100, status_filter=status)
    return ApiResponse(data=[task if isinstance(task, dict) else task.model_dump(mode='json') for task in tasks], message='成功')


@router.get('/summary', response_model=ApiResponse)
def read_workspace_summary(
    current_user: CurrentUser = Depends(get_current_user),
    workspace_path: str = Query(min_length=1, max_length=500),
) -> ApiResponse:
    """Return a Chinese summary preview for the current workspace board.

    Args:
        current_user: Authenticated user.
        workspace_path: Workspace root path.

    Returns:
        Structured board summary for quick preview.

    Raises:
        HTTPException: If the user lacks permission or the workspace path is invalid.
    """
    admin_or_leader(current_user)
    effective_workspace = _normalize_workspace_path(workspace_path)
    tasks = list_workspace_task_items(effective_workspace, limit=100)
    summary = _summarize_workspace_tasks(tasks)
    return ApiResponse(data={**summary.model_dump(), 'workspace_path': effective_workspace}, message='成功')


@router.post('/tasks/items/batch', response_model=ApiResponse, status_code=http_status.HTTP_201_CREATED)
def batch_create_task_items(
    raw_payload: dict[str, Any],
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    """批量创建工作区任务条目。

    Args:
        raw_payload: 原始请求体，支持 items/workspace_path。
        current_user: 已认证当前用户。

    Returns:
        批量创建结果。

    Raises:
        HTTPException: 当用户无权限、参数缺失或格式不合法时抛出。
    """
    admin_or_leader(current_user)
    if not isinstance(raw_payload, dict):
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail='请求体格式不合法')

    items = raw_payload.get('items')
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail='任务列表不能为空')

    workspace_path = raw_payload.get('workspace_path')
    if not isinstance(workspace_path, str) or not workspace_path.strip():
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail='workspace_path 不能为空')

    created_items: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f'第 {index} 条任务数据不合法')
        try:
            task_item = TaskItemCreate.model_validate(item)
        except ValueError as exc:
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

        created_items.append(
            upsert_workspace_task_item(
                workspace_path=workspace_path,
                task_key=task_item.task_key,
                title=task_item.title,
                status=task_item.status,
                description=task_item.description,
                assignee=task_item.assignee,
                priority=task_item.priority,
                metadata={'description': task_item.description},
            )
        )

    return ApiResponse(data={'count': len(created_items), 'items': created_items}, message='批量创建成功')


@router.get('/task-queue/tasks', response_model=ApiResponse)
def read_task_queue_tasks(
    current_user: CurrentUser = Depends(get_current_user),
    workspace: str | None = Query(default='current', min_length=1, max_length=500),
    workspace_path: str | None = Query(default=None, min_length=1, max_length=500),
    status: str | None = Query(default=None, min_length=1, max_length=40),
    limit: int = Query(default=100, ge=1, le=100),
) -> ApiResponse:
    """Read task queue tasks for frontend callers.

    Args:
        current_user: Authenticated user.
        workspace: Workspace selector.
        workspace_path: Explicit workspace path.
        status: Optional task status filter.
        limit: Maximum number of tasks to return.

    Returns:
        Structured API response with queue tasks.
    """
    admin_or_leader(current_user)
    selector = workspace_path or workspace
    if status is not None and status not in VALID_TASK_STATUSES:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail='任务状态筛选参数不合法')
    if workspace_path is None and selector is not None and selector not in {'current'} and not selector.startswith('workspace:'):
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail='工作区选择器不合法')
    effective_workspace = _normalize_workspace_path(workspace_path or _resolve_workspace_selector(selector))
    tasks = list_workspace_task_items(effective_workspace, limit=limit, status_filter=status)
    return ApiResponse(data=[task if isinstance(task, dict) else task.model_dump(mode='json') for task in tasks], message='成功')


@router.get('/tasks/items', response_model=ApiResponse)
def read_workspace_task_items(
    current_user: CurrentUser = Depends(get_current_user),
    workspace_path: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, min_length=1, max_length=40),
) -> ApiResponse:
    """Read workspace task items for recommendations.

    Args:
        current_user: Authenticated user.
        workspace_path: Workspace root path.
        limit: Maximum number of items to return.
        status: Optional task status filter.

    Returns:
        Structured API response with task items.

    Raises:
        HTTPException: If the user lacks permission or the query parameters are invalid.
    """
    admin_or_leader(current_user)
    if status is not None and status not in VALID_TASK_STATUSES:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail='任务状态筛选参数不合法')
    effective_workspace = _normalize_workspace_path(workspace_path)
    tasks = list_workspace_task_items(effective_workspace, limit=limit)
    if status is not None:
        tasks = [task for task in tasks if task.get('status') == status]
    return ApiResponse(data=[task if isinstance(task, dict) else task.model_dump(mode='json') for task in tasks], message='成功')
