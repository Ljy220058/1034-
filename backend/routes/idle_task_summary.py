from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from ..idle_card_prompts import build_idle_card_prompts
from ..models import ApiResponse
from ..worker_board import build_worker_board

router = APIRouter(prefix='/api/v1', tags=['idle-task-summary'])
DEFAULT_WORKSPACE_PATH = '/root/autodl-tmp/projects/hermes-swarm-lab'
VALID_STATUSES = {'todo', 'ready', 'running', 'blocked', 'done', 'archived'}


class IdleTaskSummaryRequest(BaseModel):
    """空闲任务摘要请求。"""

    workspace_path: str = Field(default=DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500)

    @field_validator('workspace_path', mode='after')
    @classmethod
    def normalize_workspace_path(cls, value: str) -> str:
        """规范化工作区路径。"""
        return str(Path(value).expanduser().resolve())


@dataclass(frozen=True)
class IdleTaskRecommendation:
    """单条空闲任务调度建议。"""

    worker_key: str
    name: str
    status: str
    task_id: str | None
    task_title: str | None
    reason: str

    def as_dict(self) -> dict[str, str | None]:
        """转换为 JSON 可序列化字典。"""
        return {
            'worker_key': self.worker_key,
            'name': self.name,
            'status': self.status,
            'task_id': self.task_id,
            'task_title': self.task_title,
            'reason': self.reason,
        }


def _normalize_workspace_path(workspace_path: str) -> str:
    """Normalize a workspace path.

    Args:
        workspace_path: Raw workspace path.

    Returns:
        Absolute normalized workspace path.
    """
    return str(Path(workspace_path).expanduser().resolve())


def _profile_name(worker: dict[str, Any]) -> str:
    """Extract a stable worker profile name.

    Args:
        worker: Worker row.

    Returns:
        Stable worker identifier.
    """
    return str(worker.get('worker_key') or worker.get('name') or '').strip()


def _board_tasks(board: dict[str, Any]) -> list[dict[str, Any]]:
    """提取看板中的任务列表，兼容不同快照字段。"""
    raw_tasks = board.get('recent_tasks') or board.get('recent_changes') or []
    return [task for task in raw_tasks if isinstance(task, dict)]


def _pick_recommendations(
    idle_workers: list[dict[str, Any]], pending_tasks: list[dict[str, Any]]
) -> list[IdleTaskRecommendation]:
    """Pick light dispatch recommendations for the board preview.

    Args:
        idle_workers: Idle worker rows.
        pending_tasks: Pending task rows.

    Returns:
        Recommendation rows.
    """
    recommendations: list[IdleTaskRecommendation] = []
    for index, task in enumerate(pending_tasks[:3]):
        if not idle_workers:
            break
        worker = idle_workers[index % len(idle_workers)]
        recommendations.append(
            IdleTaskRecommendation(
                worker_key=_profile_name(worker),
                name=str(worker.get('name') or worker.get('worker_key') or ''),
                status=str(worker.get('status') or 'unknown'),
                task_id=str(task.get('task_id') or task.get('task_key') or ''),
                task_title=str(task.get('title') or ''),
                reason='当前空闲且负载较低，适合优先承接该任务。',
            )
        )
    return recommendations


def _idle_workers(board: dict[str, Any]) -> list[dict[str, Any]]:
    """提取当前空闲 worker。"""
    return [worker for worker in board.get('idle_workers', []) if isinstance(worker, dict) and str(worker.get('status')) == 'active']


def _build_idle_summary(workspace_path: str) -> dict[str, Any]:
    """Build a board summary for idle-task preview.

    Args:
        workspace_path: Workspace path.

    Returns:
        Summary payload with workers and pending tasks.
    """
    normalized_workspace = _normalize_workspace_path(workspace_path)
    board = build_worker_board(normalized_workspace)
    idle_workers = _idle_workers(board)
    pending_tasks = [task for task in _board_tasks(board) if str(task.get('status')) in {'todo', 'ready', 'running', 'blocked'}]
    blocked_tasks = [task for task in pending_tasks if str(task.get('status')) == 'blocked']
    counts = Counter(str(task.get('status')) for task in pending_tasks)
    recommendations = _pick_recommendations(idle_workers, pending_tasks)
    card_prompts = build_idle_card_prompts(idle_workers, pending_tasks, threshold_minutes=60)
    return {
        'workspace_path': normalized_workspace,
        'generated_at': str(board.get('generated_at') or ''),
        'summary': {
            'idle_workers': len(idle_workers),
            'pending_tasks': len(pending_tasks),
            'blocked_tasks': len(blocked_tasks),
            'todo_tasks': counts.get('todo', 0),
            'ready_tasks': counts.get('ready', 0),
            'running_tasks': counts.get('running', 0),
            'dispatch_recommendations': len(recommendations),
            'idle_card_prompts': len(card_prompts),
        },
        'idle_workers': [
            {
                'worker_key': worker.get('worker_key'),
                'name': worker.get('name'),
                'status': worker.get('status'),
                'capabilities': list(worker.get('capabilities') or []),
                'last_seen_at': worker.get('last_seen_at'),
            }
            for worker in idle_workers[:10]
        ],
        'pending_tasks': [
            {
                'task_id': task.get('task_id') or task.get('task_key'),
                'task_key': task.get('task_key'),
                'title': task.get('title'),
                'status': task.get('status'),
                'assignee': task.get('assignee'),
                'priority': task.get('priority'),
                'updated_at': task.get('updated_at'),
            }
            for task in pending_tasks[:15]
        ],
        'recent_block_reasons': [
            {
                'task_id': task.get('task_id') or task.get('task_key'),
                'title': task.get('title'),
                'reason': str(task.get('metadata', {}).get('last_failure_reason') or task.get('last_failure_reason') or '未记录失败原因'),
            }
            for task in blocked_tasks[:5]
        ],
        'dispatch_recommendations': [recommendation.as_dict() for recommendation in recommendations],
        'idle_card_prompts': [prompt.as_dict() for prompt in card_prompts],
    }


@router.get('/idle-task-summary/summary', response_model=ApiResponse)
def read_idle_task_summary(
    workspace_path: str = Query(default=DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500),
) -> ApiResponse:
    """Return a Chinese summary for idle backend tasks.

    Args:
        workspace_path: Workspace path used to build the snapshot.

    Returns:
        Structured API response for a quick board preview.
    """
    payload = _build_idle_summary(workspace_path)
    return ApiResponse(
        data={
            'workspace_path': payload['workspace_path'],
            'generated_at': payload['generated_at'],
            'summary': payload['summary'],
            'idle_workers': payload['idle_workers'],
            'pending_tasks': payload['pending_tasks'],
            'recent_block_reasons': payload['recent_block_reasons'],
            'dispatch_recommendations': payload['dispatch_recommendations'],
            'idle_card_prompts': payload['idle_card_prompts'],
        },
        message='已返回空闲后端任务摘要',
    )


@router.get('/idle-task-summary/auto-prompts', response_model=ApiResponse)
def read_idle_card_auto_prompts(
    workspace_path: str = Query(default=DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500),
    threshold_minutes: int = Query(default=60, ge=1, le=1440),
) -> ApiResponse:
    """返回空闲 worker 长时间未领取卡片的中文自动提醒。

    Args:
        workspace_path: 工作区路径。
        threshold_minutes: 触发提醒的等待分钟数阈值。

    Returns:
        包含提醒列表和建议优先级的标准响应。
    """
    normalized_workspace = _normalize_workspace_path(workspace_path)
    board = build_worker_board(normalized_workspace)
    idle_workers = _idle_workers(board)
    prompts = build_idle_card_prompts(idle_workers, _board_tasks(board), threshold_minutes)
    return ApiResponse(
        data={
            'workspace_path': normalized_workspace,
            'threshold_minutes': threshold_minutes,
            'summary': {
                'idle_workers': len(idle_workers),
                'prompt_count': len(prompts),
            },
            'prompts': [prompt.as_dict() for prompt in prompts],
        },
        message='已生成空闲卡片自动提醒',
    )


@router.get('/idle-task-summary/sidebar', response_model=ApiResponse)
def read_idle_task_sidebar(
    workspace_path: str = Query(default=DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500),
    status: str | None = Query(default=None, max_length=20),
) -> ApiResponse:
    """Return sidebar preview data for idle backend tasks.

    Args:
        workspace_path: Workspace path used to build the snapshot.
        status: Optional status filter.

    Returns:
        Structured API response for sidebar preview.

    Raises:
        HTTPException: When the status filter is invalid.
    """
    normalized_status = status.strip().lower() if status else None
    if normalized_status and normalized_status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail='状态筛选参数无效')
    payload = _build_idle_summary(workspace_path)
    tasks = payload['pending_tasks']
    if normalized_status:
        tasks = [task for task in tasks if str(task.get('status')).lower() == normalized_status]
    summary = dict(payload['summary'])
    summary['total'] = len(payload['pending_tasks'])
    summary['running'] = summary.get('running_tasks', 0)
    summary['blocked'] = summary.get('blocked_tasks', 0)
    summary['ready'] = summary.get('ready_tasks', 0)
    summary['todo'] = summary.get('todo_tasks', 0)
    return ApiResponse(
        data={
            'workspace_path': payload['workspace_path'],
            'status_filter': normalized_status,
            'summary': summary,
            'tasks': tasks,
            'updated_at': payload['generated_at'],
        },
        message='已返回任务侧栏' if not normalized_status else f'已返回 {normalized_status} 任务侧栏',
    )


@router.get('/idle-backend-summary', response_model=ApiResponse)
def read_idle_backend_summary(workspace_path: str = Query(default=DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500)) -> ApiResponse:
    """获取空闲后端任务聚合摘要。"""
    payload = _build_idle_summary(workspace_path)
    recommended_profiles = [item['worker_key'] for item in payload['dispatch_recommendations']]
    return ApiResponse(
        data={
            'summary': payload['summary'],
            'recommendations': payload['dispatch_recommendations'],
            'recommended_profiles': recommended_profiles,
            'recent_block_reasons': payload['recent_block_reasons'],
            'idle_card_prompts': payload['idle_card_prompts'],
        },
        message='已生成空闲后端任务摘要',
    )


@router.get('/idle-backend-task-recommender', response_model=ApiResponse)
def read_idle_backend_task_recommender(workspace_path: str = Query(default=DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500)) -> ApiResponse:
    """获取空闲后端任务推荐。"""
    payload = _build_idle_summary(workspace_path)
    return ApiResponse(
        data={
            'dispatch_recommendations': payload['dispatch_recommendations'],
            'recent_block_reasons': payload['recent_block_reasons'],
            'idle_card_prompts': payload['idle_card_prompts'],
        },
        message='已生成空闲后端任务摘要',
    )
