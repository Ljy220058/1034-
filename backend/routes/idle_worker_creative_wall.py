from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..models import ApiResponse
from ..repository import list_task_queue_workers, list_workspace_task_items, upsert_workspace_task_item

router = APIRouter(prefix='/api/v1', tags=['idle-worker-creative-wall'])

_DEFAULT_WORKSPACE_PATH = '/root/autodl-tmp/projects/hermes-swarm-lab'
_SUPPORTED_WORKER_TYPES = ('backend', 'frontend', 'qa', 'docs', 'devops', 'security', 'review', 'idea')
_DISPATCHABLE_STATUSES = {'todo', 'ready'}
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
    'security': ('security', 'auth', 'token', '安全', '审计'),
    'review': ('review', 'code-review', '代码审查', 'reviewer'),
    'idea': ('idea', 'creative', '创意', '策划'),
}


@dataclass(frozen=True)
class WorkerRoleGroup:
    """空闲 worker 创意墙角色分组。"""

    worker_type: str
    idle_workers: list[dict[str, Any]]
    idea_cards: list[dict[str, Any]]

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        """序列化为 JSON 兼容字典。"""
        return {
            'worker_type': self.worker_type,
            'role': _TYPE_LABELS[self.worker_type],
            'summary': {
                'idle_worker_count': len(self.idle_workers),
                'idea_card_count': len(self.idea_cards),
            },
            'idle_workers': self.idle_workers,
            'idea_cards': self.idea_cards,
        }


class CreativeWallDispatchRequest(BaseModel):
    """空闲 worker 创意墙一键分发请求。"""

    workspace_path: str = Field(default=_DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500)
    worker_type: str | None = Field(default=None, min_length=1, max_length=40)
    task_key: str | None = Field(default=None, min_length=1, max_length=120)


def _normalize_workspace_path(workspace_path: str) -> str:
    """标准化工作区路径。

    Args:
        workspace_path: 原始工作区路径。

    Returns:
        解析后的绝对路径字符串。

    Raises:
        HTTPException: 路径为空时返回中文 422。
    """
    stripped = workspace_path.strip()
    if not stripped:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='workspace_path 不能为空')
    return str(Path(stripped).expanduser().resolve())


def _normalize_worker_type(worker_type: str | None) -> str | None:
    """校验并标准化 worker 类型筛选。

    Args:
        worker_type: 查询参数或请求体中的 worker 类型。

    Returns:
        标准化后的 worker 类型，未传时为 None。

    Raises:
        HTTPException: worker 类型不支持时返回中文 422。
    """
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
    """根据 worker key、名称与能力标签推断角色类型。"""
    text_parts = [str(worker.get('worker_key') or ''), str(worker.get('name') or '')]
    text_parts.extend(str(value) for value in list(worker.get('capabilities') or []))
    text = ' '.join(text_parts).lower()
    for worker_type, keywords in _TYPE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return worker_type
    return 'backend'


def _running_worker_keys(tasks: list[dict[str, Any]]) -> set[str]:
    """提取同工作区正在执行任务占用的 worker key。"""
    return {
        str(task.get('assignee') or '')
        for task in tasks
        if str(task.get('status')) in _RUNNING_STATUSES and task.get('assignee')
    }


def _idle_workers_by_type(worker_type: str | None, tasks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """按类型汇总当前空闲 worker。

    Args:
        worker_type: 可选 worker 类型筛选。
        tasks: 当前工作区任务列表，用于排除忙碌 worker。

    Returns:
        key 为 worker 类型、value 为空闲 worker 列表的字典。
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    busy_worker_keys = _running_worker_keys(tasks)
    workers = list_task_queue_workers()
    for worker in workers:
        if str(worker.get('status')) != 'active':
            continue
        if str(worker.get('worker_key') or '') in busy_worker_keys:
            continue
        inferred_type = _infer_worker_type(worker)
        if worker_type is not None and inferred_type != worker_type:
            continue
        groups.setdefault(inferred_type, []).append(
            {
                'worker_key': worker.get('worker_key'),
                'name': worker.get('name'),
                'status': worker.get('status'),
                'capabilities': list(worker.get('capabilities') or []),
                'last_seen_at': worker.get('last_seen_at'),
            }
        )
    return groups


def _task_matches_type(task: dict[str, Any], worker_keys: set[str], worker_type: str) -> bool:
    """判断任务是否适合当前角色分组接手。

    Args:
        task: 当前工作区任务。
        worker_keys: 当前角色分组内空闲 worker key 集合。
        worker_type: 当前角色类型。

    Returns:
        任务是否可作为该角色的创意卡片。
    """
    assignee = str(task.get('assignee') or '')
    if assignee in worker_keys:
        return True
    metadata = task.get('metadata') if isinstance(task.get('metadata'), dict) else {}
    text = ' '.join(
        str(value or '')
        for value in (task.get('title'), task.get('description'), metadata.get('lane'), metadata.get('idea'))
    ).lower()
    return any(keyword in text for keyword in _TYPE_KEYWORDS[worker_type])


def _idea_cards_for_type(tasks: list[dict[str, Any]], workers: list[dict[str, Any]], worker_type: str) -> list[dict[str, Any]]:
    """为指定角色构建可接手创意卡片。

    Args:
        tasks: 当前工作区任务列表。
        workers: 当前角色分组的空闲 worker 列表。
        worker_type: 当前角色类型。

    Returns:
        按优先级排序后的最多 6 张创意卡片。
    """
    worker_keys = {str(worker.get('worker_key') or '') for worker in workers}
    cards: list[dict[str, Any]] = []
    for task in tasks:
        if str(task.get('status')) not in _DISPATCHABLE_STATUSES:
            continue
        if not _task_matches_type(task, worker_keys, worker_type):
            continue
        metadata = task.get('metadata') if isinstance(task.get('metadata'), dict) else {}
        fit_reason = str(metadata.get('idea') or metadata.get('description') or task.get('description') or '复用现有任务数据生成可接手创意')
        suggested_action = f'交给{_TYPE_LABELS[worker_type]}处理'
        cards.append(
            {
                'task_key': task.get('task_key'),
                'task_id': task.get('task_id') or task.get('task_key'),
                'title': task.get('title'),
                'brief': str(metadata.get('summary') or task.get('description') or fit_reason),
                'suggested_action': suggested_action,
                'fit_reason': fit_reason,
                'status': task.get('status'),
                'priority': int(task.get('priority') or 0),
                'reason': fit_reason,
                'cta': suggested_action,
            }
        )
    cards.sort(key=lambda item: (-int(item['priority']), str(item['task_key'])))
    return cards[:6]


def _build_creative_wall_payload(workspace_path: str, worker_type: str | None) -> dict[str, Any]:
    """构建空闲 worker 创意墙响应体。

    Args:
        workspace_path: 工作区路径。
        worker_type: 可选 worker 类型筛选。

    Returns:
        包含 summary 与 roles 的前端最小可用 JSON。
    """
    normalized_workspace = _normalize_workspace_path(workspace_path)
    normalized_type = _normalize_worker_type(worker_type)
    tasks = list_workspace_task_items(normalized_workspace, limit=200)
    worker_groups = _idle_workers_by_type(normalized_type, tasks)
    roles = [
        WorkerRoleGroup(
            worker_type=group_type,
            idle_workers=workers,
            idea_cards=_idea_cards_for_type(tasks, workers, group_type),
        ).model_dump(mode='json')
        for group_type, workers in worker_groups.items()
    ]
    roles.sort(key=lambda item: (str(item['worker_type']), -int(item['summary']['idea_card_count'])))
    idea_card_count = sum(int(role['summary']['idea_card_count']) for role in roles)
    return {
        'workspace_path': normalized_workspace,
        'filters': {'worker_type': normalized_type},
        'summary': {
            'idle_worker_count': sum(len(workers) for workers in worker_groups.values()),
            'role_count': len(roles),
            'idea_card_count': idea_card_count,
            'running_task_count': sum(1 for task in tasks if str(task.get('status')) in _RUNNING_STATUSES),
        },
        'roles': roles,
    }


def _first_idle_worker(workers_by_type: dict[str, list[dict[str, Any]]]) -> tuple[str, dict[str, Any]] | None:
    """选择一个稳定排序后的空闲 worker。"""
    for worker_type in sorted(workers_by_type):
        workers = sorted(workers_by_type[worker_type], key=lambda item: str(item.get('worker_key') or ''))
        if workers:
            return worker_type, workers[0]
    return None


def _select_dispatch_card(
    tasks: list[dict[str, Any]],
    workers: list[dict[str, Any]],
    worker_type: str,
    task_key: str | None,
) -> dict[str, Any] | None:
    """选择要分发给空闲 worker 的创意卡片。

    Args:
        tasks: 当前工作区任务列表。
        workers: 候选 worker 列表。
        worker_type: worker 类型。
        task_key: 可选指定创意卡片键。

    Returns:
        匹配的创意卡片；没有匹配时返回 None。
    """
    cards = _idea_cards_for_type(tasks, workers, worker_type)
    if task_key is None:
        return cards[0] if cards else None
    for card in cards:
        if str(card.get('task_key') or '') == task_key:
            return card
    return None


def _dispatch_idle_worker_idea(payload: CreativeWallDispatchRequest) -> dict[str, Any]:
    """构建并落库一键分发创意结果。

    Args:
        payload: 分发请求，包含工作区、可选 worker 类型与卡片键。

    Returns:
        已分发的 worker、创意卡片与落库任务摘要。

    Raises:
        HTTPException: 没有空闲 worker 或没有可分发卡片时返回中文 404。
    """
    normalized_workspace = _normalize_workspace_path(payload.workspace_path)
    normalized_type = _normalize_worker_type(payload.worker_type)
    tasks = list_workspace_task_items(normalized_workspace, limit=200)
    workers_by_type = _idle_workers_by_type(normalized_type, tasks)
    selected_worker = _first_idle_worker(workers_by_type)
    if selected_worker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='没有可接收创意的空闲 worker')
    worker_type, worker = selected_worker
    card = _select_dispatch_card(tasks, [worker], worker_type, payload.task_key)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='没有可分发的创意卡片')
    updated = upsert_workspace_task_item(
        workspace_path=normalized_workspace,
        task_key=str(card['task_key']),
        title=str(card.get('title') or ''),
        status='ready',
        description=str(card.get('reason') or ''),
        assignee=str(worker.get('worker_key') or ''),
        priority=int(card.get('priority') or 0),
        metadata={
            'idea': card.get('reason'),
            'dispatch_source': 'idle_worker_creative_wall',
            'worker_type': worker_type,
        },
    )
    return {
        'workspace_path': normalized_workspace,
        'worker_type': worker_type,
        'worker': {
            'worker_key': worker.get('worker_key'),
            'name': worker.get('name'),
            'status': worker.get('status'),
        },
        'idea_card': card,
        'dispatch': {
            'task_key': updated.get('task_key'),
            'assignee': updated.get('assignee'),
            'status': updated.get('status'),
        },
    }


@router.get('/workers/creative-wall', response_model=ApiResponse)
def read_idle_worker_creative_wall(
    workspace_path: str = Query(default=_DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500),
    worker_type: str | None = Query(default=None, min_length=1, max_length=40),
) -> ApiResponse:
    """返回按角色聚合的空闲 worker 创意墙。

    Args:
        workspace_path: 需要汇总的工作区路径。
        worker_type: 可选 worker 类型筛选。

    Returns:
        ApiResponse，data 内包含 summary 与 roles。
    """
    payload = _build_creative_wall_payload(workspace_path, worker_type)
    return ApiResponse(data=payload, message='已生成空闲 worker 创意墙')


@router.post('/workers/creative-wall/dispatch', response_model=ApiResponse)
def dispatch_idle_worker_creative_wall(payload: CreativeWallDispatchRequest) -> ApiResponse:
    """一键把可接手创意分发给匹配的空闲 worker。

    Args:
        payload: 分发请求，包含工作区、可选 worker 类型与创意卡片键。

    Returns:
        ApiResponse，data 内包含分发结果。
    """
    data = _dispatch_idle_worker_idea(payload)
    return ApiResponse(data=data, message='已分发空闲 worker 创意')
