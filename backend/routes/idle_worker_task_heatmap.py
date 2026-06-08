from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from ..database import connect
from ..models import ApiResponse
from ..worker_recommendations import ensure_queue_schema

router = APIRouter(prefix='/api/v1/workers', tags=['idle-worker-task-heatmap'])

_ACTIVE_TASK_STATUSES = {'todo', 'ready', 'running', 'doing', 'blocked'}
_DISPATCHABLE_TASK_STATUSES = {'todo', 'ready'}
_RUNNING_TASK_STATUSES = {'running', 'doing'}


@dataclass(frozen=True)
class WorkerHeatCandidate:
    """空闲 worker 任务热度候选。"""

    worker_key: str
    name: str
    status: str
    capabilities: list[str]
    idle: bool
    last_seen_at: str
    idle_hours: float
    current_queue_length: int
    score: float
    reasons: list[str]
    recommended_task: dict[str, Any] | None

    def model_dump(self) -> dict[str, Any]:
        """转换为接口响应字典。"""
        return {
            'worker_key': self.worker_key,
            'name': self.name,
            'status': self.status,
            'capabilities': self.capabilities,
            'idle': self.idle,
            'last_seen_at': self.last_seen_at,
            'idle_hours': round(self.idle_hours, 2),
            'current_queue_length': self.current_queue_length,
            'score': round(self.score, 2),
            'reasons': self.reasons,
            'recommended_task': self.recommended_task,
        }


def _normalize_workspace_path(workspace_path: str | Path) -> str:
    """标准化工作区路径。

    Args:
        workspace_path: 查询参数中的工作区路径。

    Returns:
        绝对路径字符串。
    """
    return str(Path(workspace_path).expanduser().resolve())


def _decode_capabilities(raw_value: str | None) -> list[str]:
    """解析 worker 能力标签。"""
    if not raw_value:
        return []
    import json

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _parse_timestamp(raw_value: str | None) -> datetime | None:
    """解析 SQLite 时间戳为可比较时间。"""
    if not raw_value:
        return None
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError:
        try:
            parsed = datetime.strptime(raw_value, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _hours_since(raw_value: str | None) -> float:
    """计算距离指定时间的小时数。"""
    parsed = _parse_timestamp(raw_value)
    if parsed is None:
        return 168.0
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 3600.0)


def _list_workers() -> list[dict[str, Any]]:
    """读取 worker 队列记录。"""
    ensure_queue_schema()
    with connect() as connection:
        rows = connection.execute(
            'SELECT worker_key, name, status, capabilities, last_seen_at FROM task_queue_workers ORDER BY updated_at DESC, id DESC'
        ).fetchall()
    return [
        {
            'worker_key': row['worker_key'],
            'name': row['name'],
            'status': row['status'],
            'capabilities': _decode_capabilities(row['capabilities']),
            'last_seen_at': row['last_seen_at'],
        }
        for row in rows
    ]


def _list_tasks(workspace_path: str) -> list[dict[str, Any]]:
    """读取工作区任务队列记录。"""
    ensure_queue_schema()
    with connect() as connection:
        rows = connection.execute(
            '''
            SELECT task_key, title, status, assignee, priority, updated_at
            FROM workspace_tasks
            WHERE workspace = ?
            ORDER BY priority DESC, datetime(updated_at) DESC, id DESC
            LIMIT ?
            ''',
            (workspace_path, 200),
        ).fetchall()
    return [
        {
            'task_key': row['task_key'],
            'title': row['title'],
            'status': row['status'],
            'assignee': row['assignee'],
            'priority': int(row['priority'] or 0),
            'updated_at': row['updated_at'],
        }
        for row in rows
    ]


def _recommended_task(tasks: list[dict[str, Any]]) -> dict[str, Any] | None:
    """选择优先派发任务。"""
    dispatchable = [task for task in tasks if str(task['status']) in _DISPATCHABLE_TASK_STATUSES]
    if not dispatchable:
        return None
    task = dispatchable[0]
    return {
        'task_key': task['task_key'],
        'title': task['title'],
        'status': task['status'],
        'priority': task['priority'],
    }


def _queue_length(worker_key: str, worker_name: str, tasks: list[dict[str, Any]]) -> int:
    """统计 worker 当前队列长度。"""
    return sum(
        1
        for task in tasks
        if str(task.get('status')) in _ACTIVE_TASK_STATUSES
        and str(task.get('assignee') or '') in {worker_key, worker_name}
    )


def _build_candidate(worker: dict[str, Any], tasks: list[dict[str, Any]]) -> WorkerHeatCandidate:
    """计算单个 worker 任务热度。"""
    worker_key = str(worker['worker_key'])
    worker_name = str(worker['name'])
    status_value = str(worker['status'])
    queue_length = _queue_length(worker_key, worker_name, tasks)
    idle = status_value == 'active' and queue_length == 0
    idle_hours = _hours_since(str(worker.get('last_seen_at') or ''))
    dispatchable_queue_length = sum(1 for task in tasks if str(task['status']) in _DISPATCHABLE_TASK_STATUSES)
    score = 0.0
    reasons: list[str] = []

    if idle:
        score += 60.0
        reasons.append('worker 处于 active 且当前无排队任务')
    elif status_value == 'active':
        score += 35.0
        reasons.append(f'worker 仍 active，但当前队列长度为 {queue_length}')
    elif status_value == 'paused':
        score += 12.0
        reasons.append('worker 暂停，仅作为兜底候选')
    else:
        score -= 20.0
        reasons.append('worker 不可用，暂不建议分配')

    score += min(idle_hours, 24.0) * 0.8
    reasons.append(f'最近接单距今 {idle_hours:.1f} 小时')
    score += min(dispatchable_queue_length * 5.0, 25.0)
    reasons.append(f'当前可派发队列长度为 {dispatchable_queue_length}')
    score -= queue_length * 18.0
    if queue_length:
        reasons.append('低队列长度优先，已有任务会降低热度')

    return WorkerHeatCandidate(
        worker_key=worker_key,
        name=worker_name,
        status=status_value,
        capabilities=list(worker.get('capabilities') or []),
        idle=idle,
        last_seen_at=str(worker.get('last_seen_at') or ''),
        idle_hours=idle_hours,
        current_queue_length=queue_length,
        score=score,
        reasons=reasons,
        recommended_task=_recommended_task(tasks) if idle else None,
    )


def _build_idle_worker_heatmap(workspace_path: str, limit: int) -> dict[str, Any]:
    """构建空闲 worker 任务热度图。"""
    workers = _list_workers()
    tasks = _list_tasks(workspace_path)
    candidates = [_build_candidate(worker, tasks) for worker in workers]
    candidates.sort(key=lambda item: (-item.score, item.current_queue_length, item.worker_key))
    active_tasks = [task for task in tasks if str(task['status']) in _ACTIVE_TASK_STATUSES]
    dispatchable_tasks = [task for task in tasks if str(task['status']) in _DISPATCHABLE_TASK_STATUSES]
    return {
        'workspace_path': workspace_path,
        'summary': {
            'worker_count': len(workers),
            'candidate_count': min(len(candidates), limit),
            'active_queue_length': len(active_tasks),
            'dispatchable_queue_length': len(dispatchable_tasks),
        },
        'candidates': [candidate.model_dump() for candidate in candidates[:limit]],
    }


@router.get('/idle-task-heatmap', response_model=ApiResponse)
def read_idle_worker_task_heatmap(
    workspace_path: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=10, ge=1, le=50),
) -> ApiResponse:
    """返回适合调度器使用的空闲 worker 任务热度候选列表。

    Args:
        workspace_path: 工作区路径。
        limit: 最大候选数量。

    Returns:
        包含候选 worker、热度分数和推荐任务的统一响应。

    Raises:
        HTTPException: 工作区路径无效时返回 422。
    """
    try:
        normalized_workspace = _normalize_workspace_path(workspace_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='工作区路径无效') from exc
    return ApiResponse(data=_build_idle_worker_heatmap(normalized_workspace, limit), message='已生成空闲 worker 任务热度图')
