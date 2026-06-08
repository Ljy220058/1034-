from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query

from ..models import ApiResponse
from ..worker_board import build_worker_board
from .common import CurrentUser, admin_or_leader, get_current_user

router = APIRouter(prefix='/api/v1', tags=['idle-backend-task-recommender'])

DEFAULT_WORKSPACE_PATH = '/root/autodl-tmp/projects/hermes-swarm-lab'
_CHINESE_PROFILES: tuple[str, ...] = (
    'backend-dev',
    'code-reviewer',
    'backend-optimizer',
    'backend-builder',
    'api-designer',
    'task-planner',
)


def _normalize_workspace_path(workspace_path: str) -> str:
    """标准化工作区路径。

    Args:
        workspace_path: 查询参数中的原始工作区路径。

    Returns:
        绝对工作区路径。
    """
    return str(Path(workspace_path).expanduser().resolve())


def _worker_key(worker: dict[str, object]) -> str:
    """提取 worker profile 名称。

    Args:
        worker: worker 看板中的 worker 记录。

    Returns:
        worker_key 或 name 字段。
    """
    value = worker.get('worker_key') or worker.get('name') or ''
    return str(value)


def _candidate_profiles(workspace_path: str) -> list[str]:
    """按空闲与低负载优先级返回候选 profile。

    Args:
        workspace_path: 用于读取 worker 看板的工作区路径。

    Returns:
        按优先级排序的 profile 名称列表。
    """
    board = build_worker_board(workspace_path, refresh=False)
    idle_profiles = [_worker_key(worker) for worker in board.get('idle_workers', []) if isinstance(worker, dict)]
    busy_profiles = {_worker_key(worker) for worker in board.get('busy_workers', []) if isinstance(worker, dict)}
    preferred_idle = [profile for profile in _CHINESE_PROFILES if profile in idle_profiles]
    preferred_low_load = [profile for profile in _CHINESE_PROFILES if profile not in preferred_idle and profile not in busy_profiles]
    fallback = [profile for profile in _CHINESE_PROFILES if profile not in preferred_idle and profile not in preferred_low_load]
    return preferred_idle + preferred_low_load + fallback


def _task_seed(title: str, index: int) -> str:
    """构造中文任务种子。

    Args:
        title: 任务标题。
        index: 1 开始的序号。

    Returns:
        中文任务种子文本。
    """
    seeds = (
        '补全一个可直接进入看板的 FastAPI 端点',
        '为 SQLite 查询补一组可回归测试',
        '修复一个结构化错误返回的 API 分支',
        '拆分一个过长的后端模块',
    )
    phrase = seeds[(index - 1) % len(seeds)]
    return f'{phrase}：围绕「{title}」'


def _task_body(description: str) -> str:
    """生成可直接进入看板的任务正文。

    Args:
        description: 任务描述。

    Returns:
        中文看板任务正文。
    """
    return (
        f'{description}\n\n'
        '验收标准：新增或修复一个可运行 API 端点；pytest 全绿；'
        '接口返回 {"data": ..., "message": "中文"}；'
        '错误返回 {"detail": "中文描述"}。'
    )


def _generate_task_cards(workspace_path: str) -> list[dict[str, object]]:
    """生成两条可直接进入看板的中文创意任务。"""
    task_pairs = (
        {
            'title': '中文创意：任务队列空闲 profile 摘要接口',
            'description': '产出一个 FastAPI 只读接口，汇总当前空闲后端 profile、忙碌 profile 和可派发建议。',
            'recommendation_reason': '看板已有多次空闲任务分发需求，先做摘要接口可以减少人工筛选队列状态的时间。',
            'estimated_workload': '0.5 天：1 个路由、3-5 个 pytest 用例、1 次 httpx 手动验证。',
            'suitable_reason': '实现集中在 FastAPI 响应编排与现有 worker 看板读取，适合空闲后端 profile 快速交付。',
        },
        {
            'title': '中文创意：后端任务卡片合规校验接口',
            'description': '产出一个 FastAPI 校验接口，检查候选任务卡是否包含 assignee、workspace、验收标准和错误返回约束。',
            'recommendation_reason': '创意任务入队前增加合规校验，可降低协议违规、缺少验收标准和错误格式不统一的问题。',
            'estimated_workload': '0.5-1 天：请求模型、校验分支、结构化错误和 pytest 覆盖。',
            'suitable_reason': '主要是 Pydantic/FastAPI 校验逻辑，不依赖前端或部署，适合后端空闲 profile 独立处理。',
        },
    )
    profiles = _candidate_profiles(workspace_path)
    cards: list[dict[str, object]] = []
    for index, task in enumerate(task_pairs, start=1):
        title = str(task['title'])
        description = str(task['description'])
        cards.append(
            {
                'title': title,
                'description': description,
                'body': _task_body(description),
                'assignee_profile': profiles[(index - 1) % len(profiles)],
                'workspace_kind': 'dir',
                'workspace_path': workspace_path,
                'priority': 50 - index,
                'seed': _task_seed(title, index),
                'recommendation_reason': task['recommendation_reason'],
                'estimated_workload': task['estimated_workload'],
                'suitable_reason': task['suitable_reason'],
            }
        )
    return cards


def _normalize_task_cards(workspace_path: str) -> list[dict[str, object]]:
    """构造标准化任务卡片。

    Args:
        workspace_path: 任务指定工作区路径。

    Returns:
        两条标准化任务卡片。
    """
    cards = _generate_task_cards(workspace_path)
    return [
        {
            'title': card['title'],
            'description': card['description'],
            'body': card['body'],
            'assignee_profile': card['assignee_profile'],
            'workspace_kind': card['workspace_kind'],
            'workspace_path': card['workspace_path'],
            'priority': card['priority'],
            'seed': card['seed'],
            'recommendation_reason': card['recommendation_reason'],
            'estimated_workload': card['estimated_workload'],
            'suitable_reason': card['suitable_reason'],
        }
        for card in cards[:2]
    ]


@router.get('/creative-task-generator', response_model=ApiResponse)
def read_creative_task_generator(
    current_user: CurrentUser = Depends(get_current_user),
    workspace_path: str = Query(default=DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500),
) -> ApiResponse:
    """返回两条中文创意任务建议。"""
    admin_or_leader(current_user)
    normalized_workspace = _normalize_workspace_path(workspace_path)
    cards = _normalize_task_cards(normalized_workspace)
    return ApiResponse(data={'count': len(cards), 'tasks': cards}, message='成功')


@router.post('/creative-task-generator', response_model=ApiResponse, status_code=201)
def create_creative_task_generator(
    current_user: CurrentUser = Depends(get_current_user),
    workspace_path: str = Query(default=DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500),
) -> ApiResponse:
    """生成两条中文创意任务建议。"""
    admin_or_leader(current_user)
    normalized_workspace = _normalize_workspace_path(workspace_path)
    cards = _normalize_task_cards(normalized_workspace)
    return ApiResponse(data={'count': len(cards), 'tasks': cards}, message='成功')
