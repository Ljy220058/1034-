from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from ..models import ApiResponse
from ..repository import list_task_queue_workers, list_workspace_task_items

router = APIRouter(prefix='/api/v1/workers', tags=['workers'])

_SUPPORTED_WORKER_TYPES = ('backend', 'frontend', 'qa', 'docs', 'devops', 'security', 'review', 'idea')
_RUNNING_STATUSES = {'running', 'doing'}
_TYPE_LABELS = {
    'backend': '后端开发',
    'frontend': '前端开发',
    'qa': '测试验证',
    'docs': '文档撰写',
    'devops': '部署运维',
    'security': '安全审计',
    'review': '代码审查',
    'idea': '创意策划',
}
_TYPE_KEYWORDS = {
    'backend': ('backend', 'fastapi', 'sqlite', 'api', '后端', '接口', '数据库'),
    'frontend': ('frontend', 'ui', 'css', 'html', '页面', '前端'),
    'qa': ('qa', 'pytest', 'test', '测试', '验证'),
    'docs': ('docs', 'doc', 'readme', '文档', '指南'),
    'devops': ('devops', 'deploy', 'docker', 'nginx', '部署', '运维'),
    'security': ('security', 'audit', '安全', '审计'),
    'review': ('review', 'code-review', '代码审查', 'reviewer'),
    'idea': ('idea', 'creative', '创意', '策划'),
}


@dataclass(frozen=True)
class IdleWorkerIdea:
    """空闲 worker 功能创意建议。"""

    worker_type: str
    title: str
    description: str
    recommended_assignee: str
    source: dict[str, Any]

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        """序列化为稳定响应结构。

        Args:
            mode: 序列化模式，保留该参数以兼容 Pydantic 调用习惯。

        Returns:
            可 JSON 序列化的创意建议字典。
        """
        return {
            'type': self.worker_type,
            'title': self.title,
            'description': self.description,
            'recommended_assignee': self.recommended_assignee,
            'source': self.source,
        }


def _normalize_workspace_path(workspace_path: str) -> str:
    """标准化工作区路径。

    Args:
        workspace_path: 请求传入的工作区路径。

    Returns:
        解析后的绝对路径字符串。

    Raises:
        HTTPException: 路径为空时返回 422。
    """
    cleaned = workspace_path.strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='workspace_path 不能为空')
    return str(Path(cleaned).expanduser().resolve())


def _normalize_worker_type(worker_type: str | None) -> str | None:
    """校验并标准化 worker 类型筛选。"""
    if worker_type is None or not worker_type.strip():
        return None
    normalized = worker_type.strip().lower()
    if normalized not in _SUPPORTED_WORKER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='worker_type 仅支持 backend、frontend、qa、docs、devops、security、review、idea',
        )
    return normalized


def _infer_worker_type(worker: dict[str, Any]) -> str:
    """根据 worker 标识、名称和能力标签推断类型。"""
    text_parts = [str(worker.get('worker_key') or ''), str(worker.get('name') or '')]
    text_parts.extend(str(value) for value in list(worker.get('capabilities') or []))
    text = ' '.join(text_parts).lower()
    for worker_type, keywords in _TYPE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return worker_type
    return 'backend'


def _idle_workers(worker_type: str | None) -> list[dict[str, Any]]:
    """读取并筛选当前可推荐的空闲 worker。"""
    workers: list[dict[str, Any]] = []
    for worker in list_task_queue_workers():
        if str(worker.get('status')) != 'active':
            continue
        inferred_type = _infer_worker_type(worker)
        if worker_type is not None and inferred_type != worker_type:
            continue
        workers.append(
            {
                'worker_key': str(worker.get('worker_key') or ''),
                'worker_type': inferred_type,
                'name': worker.get('name'),
                'capabilities': list(worker.get('capabilities') or []),
            }
        )
    return workers


def _load_by_assignee(tasks: list[dict[str, Any]]) -> dict[str, int]:
    """统计执行中任务负载。"""
    load: dict[str, int] = {}
    for task in tasks:
        assignee = str(task.get('assignee') or '')
        if not assignee or str(task.get('status')) not in _RUNNING_STATUSES:
            continue
        load[assignee] = load.get(assignee, 0) + 1
    return load


def _best_task_for_type(tasks: list[dict[str, Any]], worker_type: str) -> dict[str, Any] | None:
    """查找最贴合指定类型的待处理任务。"""
    keywords = _TYPE_KEYWORDS[worker_type]
    candidates: list[dict[str, Any]] = []
    for task in tasks:
        if str(task.get('status')) not in {'todo', 'ready'}:
            continue
        metadata = task.get('metadata') if isinstance(task.get('metadata'), dict) else {}
        text = ' '.join(str(value or '') for value in (task.get('title'), task.get('description'), metadata.get('idea'))).lower()
        if any(keyword in text for keyword in keywords):
            candidates.append(task)
    candidates.sort(key=lambda item: (-int(item.get('priority') or 0), str(item.get('task_key') or '')))
    return candidates[0] if candidates else None


def _build_suggestion(worker: dict[str, Any], tasks: list[dict[str, Any]], sequence: int) -> IdleWorkerIdea:
    """为一个空闲 worker 生成一条可执行中文功能创意。"""
    worker_type = str(worker['worker_type'])
    worker_key = str(worker['worker_key'])
    label = _TYPE_LABELS[worker_type]
    task = _best_task_for_type(tasks, worker_type)
    if task is not None:
        title = f'中文功能：{label}接手「{task.get("title")}」增强卡片'
        description = (
            f'基于现有 {task.get("status")} 任务生成可直接创建为任务的执行建议：整理「{task.get("title")}」的输入、验收口径和接口返回结构，'
            f'交给 {worker_key} 在当前空闲窗口完成。'
        )
        source = {'kind': 'existing_task', 'task_key': task.get('task_key'), 'status': task.get('status')}
    else:
        title = f'中文功能：{label}空闲补位第 {sequence} 项'
        description = f'当前 {worker_key} 处于空闲状态，可直接创建为任务：补齐一项{label}小功能，要求产出稳定结构、中文说明和可验证结果。'
        source = {'kind': 'idle_worker', 'task_key': None, 'status': None}
    return IdleWorkerIdea(
        worker_type=worker_type,
        title=title[:120],
        description=description,
        recommended_assignee=worker_key,
        source=source,
    )


def _build_payload(workspace_path: str, worker_type: str | None) -> dict[str, Any]:
    """构建空闲 worker 功能创意推荐响应体。"""
    normalized_workspace = _normalize_workspace_path(workspace_path)
    normalized_type = _normalize_worker_type(worker_type)
    workers = _idle_workers(normalized_type)
    tasks = list_workspace_task_items(normalized_workspace, limit=200)
    load = _load_by_assignee(tasks)
    workers.sort(key=lambda item: (load.get(str(item['worker_key']), 0), str(item['worker_type']), str(item['worker_key'])))
    selected_workers = workers[:2]
    if len(selected_workers) == 1:
        selected_workers = [selected_workers[0], selected_workers[0]]
    suggestions = [_build_suggestion(worker, tasks, index + 1).model_dump(mode='json') for index, worker in enumerate(selected_workers)]
    return {
        'workspace_path': normalized_workspace,
        'filters': {'worker_type': normalized_type},
        'summary': {
            'idle_worker_count': len(workers),
            'running_task_count': sum(1 for task in tasks if str(task.get('status')) in _RUNNING_STATUSES),
            'suggestion_count': len(suggestions),
        },
        'suggestions': suggestions,
    }


@router.get('/idle-ideas', response_model=ApiResponse)
def read_idle_worker_ideas(
    workspace_path: str = Query(min_length=1, max_length=500),
    worker_type: str | None = Query(default=None, min_length=1, max_length=40),
) -> ApiResponse:
    """返回两条可直接创建任务的空闲 worker 中文功能创意建议。

    Args:
        workspace_path: 工作区绝对路径。
        worker_type: 可选 worker 类型筛选。

    Returns:
        包含标题、描述和推荐负责人的稳定创意建议响应。
    """
    payload = _build_payload(workspace_path, worker_type)
    return ApiResponse(data=payload, message='已生成空闲 worker 功能创意建议')
