from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .worker_recommendations import QueueWorker, WorkspaceQueueTask, list_queue_tasks, list_queue_workers

TASK_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    'backend': ('后端', 'api', 'fastapi', 'sqlite', '数据库', 'backend', 'server'),
    'frontend': ('前端', '页面', 'ui', 'html', 'css', 'react', 'vue', 'frontend'),
    'test': ('测试', 'pytest', '回归', '验证', 'test', 'qa'),
    'review': ('评审', '审查', 'review', '安全', 'security'),
}


@dataclass(frozen=True)
class RoutedWorker:
    """Worker routing decision result.

    Attributes:
        payload: API response payload.
        selected_worker_key: Selected worker key.
    """

    payload: dict[str, Any]
    selected_worker_key: str


def infer_task_type(title: str, description: str) -> tuple[str, list[str]]:
    """Infer task type from task text.

    Args:
        title: Task title.
        description: Task description.

    Returns:
        Inferred task type and human-readable decision reasons.
    """
    content = f'{title} {description}'.lower()
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


def _worker_matches_type(worker: QueueWorker, task_type: str) -> tuple[bool, list[str]]:
    """Check whether a worker matches the inferred task type.

    Args:
        worker: Queue worker row.
        task_type: Inferred task type.

    Returns:
        Match flag and scoring reasons.
    """
    keywords = TASK_TYPE_KEYWORDS.get(task_type, ())
    capability_text = ' '.join([worker.worker_key, worker.name, *worker.capabilities]).lower()
    matched = [keyword for keyword in keywords if keyword.lower() in capability_text]
    if not matched:
        return False, ['能力未命中任务类型，作为兜底候选']
    return True, [f'能力命中 {", ".join(matched[:4])}']


def _running_load_by_worker(tasks: list[WorkspaceQueueTask]) -> dict[str, int]:
    """Count running tasks by assignee.

    Args:
        tasks: Workspace task rows.

    Returns:
        Mapping from worker key/name to running task count.
    """
    loads: dict[str, int] = {}
    for task in tasks:
        if task.status in {'running', 'doing'} and task.assignee:
            loads[task.assignee] = loads.get(task.assignee, 0) + 1
    return loads


def _task_counts(tasks: list[WorkspaceQueueTask]) -> dict[str, int]:
    """Count board tasks by status group.

    Args:
        tasks: Workspace task rows.

    Returns:
        Summary counts for board state.
    """
    return {
        'total_tasks': len(tasks),
        'running_tasks': sum(1 for task in tasks if task.status in {'running', 'doing'}),
        'dispatchable_tasks': sum(1 for task in tasks if task.status in {'todo', 'ready'}),
        'blocked_tasks': sum(1 for task in tasks if task.status == 'blocked'),
    }


def route_task_to_worker(
    *,
    workspace_path: str | Path,
    task_key: str,
    title: str,
    description: str,
    priority: int,
) -> RoutedWorker | None:
    """Select the best active worker for a task using type and idle load.

    Args:
        workspace_path: Workspace root path.
        task_key: Task key to route.
        title: Task title.
        description: Task description.
        priority: Task priority.

    Returns:
        Routing result, or None when no active worker exists.
    """
    workers = [worker for worker in list_queue_workers() if worker.status == 'active']
    if not workers:
        return None

    tasks = list_queue_tasks(workspace_path, limit=200)
    task_type, type_reasons = infer_task_type(title, description)
    load_map = _running_load_by_worker(tasks)
    candidates: list[dict[str, Any]] = []

    for worker in workers:
        matched, match_reasons = _worker_matches_type(worker, task_type)
        running_load = load_map.get(worker.worker_key, load_map.get(worker.name, 0))
        score = (100 if matched else 20) - running_load * 10 + priority
        candidates.append(
            {
                'worker_key': worker.worker_key,
                'name': worker.name,
                'status': worker.status,
                'capabilities': worker.capabilities,
                'score': score,
                'load': {'running_tasks': running_load},
                'reasons': match_reasons + [f'当前运行任务数 {running_load}'],
            }
        )

    candidates.sort(key=lambda item: (-int(item['score']), int(item['load']['running_tasks']), str(item['worker_key'])))
    chosen = candidates[0]
    decision_log = [*type_reasons, f"低负载优先，选择 {chosen['worker_key']}（运行中 {chosen['load']['running_tasks']} 个）"]
    payload = {
        'task_key': task_key,
        'task_type': task_type,
        'workspace_path': str(Path(workspace_path).expanduser().resolve()),
        'selected_worker': chosen,
        'candidates': candidates,
        'board_summary': _task_counts(tasks),
        'decision_log': decision_log,
    }
    return RoutedWorker(payload=payload, selected_worker_key=str(chosen['worker_key']))
