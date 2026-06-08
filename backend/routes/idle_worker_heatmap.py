from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from ..models import ApiResponse
from ..worker_recommendations import build_worker_board, default_worker_digest_workspace, list_queue_tasks, list_queue_workers
from ..workspace import normalize_workspace_path

router = APIRouter(prefix='/api/v1', tags=['idle-worker-heatmap'])

_DEFAULT_WORKSPACE_PATH = '/root/autodl-tmp/projects/hermes-swarm-lab'


@dataclass(frozen=True)
class HeatmapCandidate:
    """任务热度候选。

    Attributes:
        task_key: 任务键。
        title: 任务标题。
        assignee: 当前负责人。
        score: 热度分数。
        reasons: 评分原因。
        recommended_workers: 候选 worker 列表。
    """

    task_key: str
    title: str
    assignee: str | None
    score: float
    reasons: list[str]
    recommended_workers: list[dict[str, Any]]

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        """序列化为 JSON 兼容字典。"""
        return {
            'task_key': self.task_key,
            'title': self.title,
            'assignee': self.assignee,
            'score': round(self.score, 2),
            'reasons': self.reasons,
            'recommended_workers': self.recommended_workers,
        }


def _normalize_workspace(workspace_path: str | None) -> str:
    """标准化工作区路径。

    Args:
        workspace_path: 原始工作区路径。

    Returns:
        标准化后的绝对路径。
    """
    normalized = default_worker_digest_workspace(workspace_path or _DEFAULT_WORKSPACE_PATH)
    return normalize_workspace_path(normalized)


def _parse_timestamp(raw_value: Any) -> datetime | None:
    """解析时间戳。

    Args:
        raw_value: 原始时间值。

    Returns:
        可比较的 datetime，失败返回 None。
    """
    if raw_value in (None, ''):
        return None
    if isinstance(raw_value, datetime):
        return raw_value if raw_value.tzinfo is not None else raw_value.replace(tzinfo=timezone.utc)
    if not isinstance(raw_value, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _hours_since(timestamp: datetime | None) -> float:
    """计算距离当前的小时数。"""
    if timestamp is None:
        return 168.0
    return max(0.0, (datetime.now(timezone.utc) - timestamp).total_seconds() / 3600.0)


def _queue_depth(board: dict[str, Any]) -> int:
    """统计当前队列长度。"""
    tasks = board.get('recent_tasks', [])
    return sum(1 for task in tasks if isinstance(task, dict) and str(task.get('status')) in {'todo', 'ready', 'running', 'blocked'})


def _build_heatmap_candidates(workspace_path: str, limit: int) -> list[HeatmapCandidate]:
    """构建任务热度候选列表。

    Args:
        workspace_path: 工作区路径。
        limit: 候选数量上限。

    Returns:
        按热度排序的候选列表。
    """
    board = build_worker_board(workspace_path)
    workers = [worker for worker in list_queue_workers() if isinstance(worker, dict)]
    worker_index = {str(worker.get('worker_key') or worker.get('name') or ''): worker for worker in workers}
    queue_depth = _queue_depth(board)
    tasks = list_queue_tasks(workspace_path)
    candidates: list[HeatmapCandidate] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        status_value = str(task.get('status') or '')
        if status_value not in {'todo', 'ready', 'running', 'blocked'}:
            continue
        assignee = task.get('assignee')
        assignee_key = str(assignee or '')
        worker = worker_index.get(assignee_key)
        worker_status = str(worker.get('status') if worker else '')
        last_seen = _parse_timestamp(worker.get('last_seen_at') if worker else None)
        idle_hours = _hours_since(last_seen)
        priority = int(task.get('priority') or 0)
        updated_at = _parse_timestamp(task.get('updated_at'))
        age_hours = _hours_since(updated_at)
        score = 0.0
        reasons: list[str] = []
        if status_value == 'blocked':
            score += 38.0
            reasons.append('任务处于阻塞状态')
        elif status_value == 'ready':
            score += 28.0
            reasons.append('任务已就绪可派发')
        elif status_value == 'running':
            score += 18.0
            reasons.append('任务正在执行中')
        else:
            score += 10.0
            reasons.append('任务仍在待办队列')
        score += min(queue_depth * 2.0, 20.0)
        if queue_depth:
            reasons.append(f'当前队列长度为 {queue_depth}')
        if priority > 0:
            bonus = min(priority / 10.0, 10.0)
            score += bonus
            reasons.append(f'优先级 {priority}')
        if worker is None:
            score += 8.0
            reasons.append('暂无明确负责人')
        elif worker_status == 'active' and idle_hours >= 1.0:
            score += 12.0
            reasons.append(f'负责人已空闲 {idle_hours:.1f} 小时')
        elif worker_status == 'paused':
            score -= 4.0
            reasons.append('负责人处于暂停状态')
        elif worker_status == 'disabled':
            score -= 8.0
            reasons.append('负责人已禁用')
        if age_hours >= 24.0:
            score += 6.0
            reasons.append(f'任务已更新时间超过 {age_hours:.1f} 小时')
        recommended_workers = []
        for worker_item in workers[:3]:
            recommended_workers.append(
                {
                    'worker_key': worker_item.get('worker_key'),
                    'name': worker_item.get('name'),
                    'status': worker_item.get('status'),
                    'capabilities': list(worker_item.get('capabilities') or []),
                }
            )
        candidates.append(
            HeatmapCandidate(
                task_key=str(task.get('task_key') or task.get('task_id') or ''),
                title=str(task.get('title') or ''),
                assignee=assignee_key or None,
                score=score,
                reasons=reasons,
                recommended_workers=recommended_workers,
            )
        )
    candidates.sort(key=lambda item: (-item.score, item.task_key))
    return candidates[:limit]


@router.get('/workers/heatmap', response_model=ApiResponse)
def read_worker_heatmap(
    workspace_path: str = Query(default=_DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500),
    limit: int = Query(default=10, ge=1, le=50),
) -> ApiResponse:
    """计算 worker 空闲任务热度并返回候选列表。

    Args:
        workspace_path: 工作区选择器或绝对路径。
        limit: 返回候选数量上限。

    Returns:
        包含热度分数、原因和候选 worker 的 ApiResponse。

    Raises:
        HTTPException: 当工作区路径为空时返回 422。
    """
    try:
        normalized_workspace = _normalize_workspace(workspace_path)
        candidates = [candidate.model_dump(mode='json') for candidate in _build_heatmap_candidates(normalized_workspace, limit)]
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='工作区数据不存在') from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='工作区路径无效') from exc
    return ApiResponse(
        data={
            'workspace_path': normalized_workspace,
            'summary': {
                'total_candidates': len(candidates),
                'limit': limit,
            },
            'candidates': candidates,
        },
        message='已生成任务热度图',
    )
