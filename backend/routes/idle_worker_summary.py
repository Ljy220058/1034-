from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from ..models import ApiResponse
from ..worker_board import build_worker_board
from ..worker_digest import build_worker_digest_payload, default_worker_digest_workspace

router = APIRouter(prefix='/api/v1', tags=['idle-worker-summary'])


@dataclass(frozen=True)
class IdleWorkerSummary:
    """空闲 worker 摘要。"""

    workspace_path: str
    summary: dict[str, int]
    idle_workers: list[dict[str, Any]]
    pending_tasks: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        """序列化为 JSON 兼容字典。"""
        return {
            'workspace_path': self.workspace_path,
            'summary': self.summary,
            'idle_workers': self.idle_workers,
            'pending_tasks': self.pending_tasks,
            'recommendations': self.recommendations,
        }


_DEFAULT_WORKSPACE_PATH = '/root/autodl-tmp/projects/hermes-swarm-lab'


def _normalize_workspace_path(workspace_path: str) -> str:
    """标准化工作区路径。"""
    return str(Path(workspace_path).expanduser().resolve())


def _idle_workers(board: dict[str, Any]) -> list[dict[str, Any]]:
    """提取空闲 worker 列表。"""
    workers = board.get('idle_workers', [])
    return [worker for worker in workers if isinstance(worker, dict) and str(worker.get('status')) == 'active']


def _pending_tasks(board: dict[str, Any]) -> list[dict[str, Any]]:
    """提取待处理任务列表。"""
    tasks = board.get('recent_tasks', [])
    return [task for task in tasks if isinstance(task, dict) and str(task.get('status')) in {'todo', 'ready', 'running', 'blocked'}]


def _recommendation_candidates() -> list[dict[str, Any]]:
    """构建推荐候选。"""
    return [
        {
            'title': '中文创意：空闲后端任务验收证据归档接口',
            'description': '新增只读 FastAPI 接口，汇总近期后端任务的测试命令、手动验证结果和修改文件路径，方便 reviewer 快速验收。',
            'workload': '0.5 天：1 个路由、1 个轻量服务函数、3 个 pytest 用例、1 次 httpx 手动验证。',
            'reason': '主要是读取现有任务快照并编排中文响应，不涉及前端和部署，适合后端 profile 快速独立交付。',
            'priority': 1,
        },
        {
            'title': '中文创意：后端 API 错误格式巡检接口',
            'description': '新增一个 FastAPI 巡检接口，扫描后端路由元数据并返回可能未使用 {"detail": "中文描述"} 的错误路径清单。',
            'workload': '0.5-1 天：路由扫描、错误格式规则、边界用例和结构化响应测试。',
            'reason': '任务聚焦 FastAPI 路由与错误响应规范，能直接提升后续后端任务质量，适合空闲后端 profile。',
            'priority': 2,
        },
    ]


def _build_summary_payload(workspace_path: str) -> dict[str, Any]:
    """构建空闲后端摘要返回体。"""
    normalized_workspace = _normalize_workspace_path(workspace_path)
    board = build_worker_board(normalized_workspace)
    idle_workers = _idle_workers(board)
    pending_tasks = _pending_tasks(board)
    recommendations = sorted(_recommendation_candidates(), key=lambda item: item['priority'])
    summary = board.get('summary', {})
    return {
        'workspace_path': normalized_workspace,
        'summary': {
            'idle_workers': len(idle_workers),
            'pending_tasks': len(pending_tasks),
            'running_tasks': int(summary.get('running_tasks') or summary.get('running') or 0),
            'blocked_tasks': int(summary.get('blocked_tasks') or summary.get('blocked') or 0),
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
            }
            for task in pending_tasks[:10]
        ],
        'recommendations': recommendations,
    }


@router.get('/workers/idle-summary', response_model=ApiResponse)
def read_idle_worker_summary(workspace_path: str = Query(default=_DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500)) -> ApiResponse:
    """获取空闲 worker 聚合摘要。"""
    payload = _build_summary_payload(workspace_path)
    return ApiResponse(data=payload, message='已生成空闲 worker 摘要')


@router.get('/workers/idle-recommendations', response_model=ApiResponse)
def read_idle_worker_recommendations(
    workspace_path: str = Query(default=_DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500),
) -> ApiResponse:
    """返回空闲 worker 可执行推荐。"""
    payload = _build_summary_payload(workspace_path)
    data = {
        'workspace_path': payload['workspace_path'],
        'summary': payload['summary'],
        'recommendations': payload['recommendations'],
        'tasks': payload['pending_tasks'],
        'snapshot': {},
    }
    return ApiResponse(data=data, message='已生成空闲 worker 可执行推荐')


@router.get('/workers/digest', response_model=ApiResponse)
def read_worker_digest(workspace_path: str | None = None, include_health: bool = True) -> ApiResponse:
    """返回 worker 总览摘要。"""
    normalized = default_worker_digest_workspace(workspace_path)
    return ApiResponse(data=build_worker_digest_payload(normalized, include_health=include_health), message='成功')


@router.get('/workers/summary', response_model=ApiResponse)
def read_worker_summary(workspace_path: str | None = None) -> ApiResponse:
    """返回 worker 结构化摘要。"""
    normalized = default_worker_digest_workspace(workspace_path)
    digest = build_worker_digest_payload(normalized)
    return ApiResponse(
        data={
            'workspace_path': normalized,
            'summary_text': digest['summary_text'],
            'copy_hint': digest['copy_hint'],
            'worker_counts': digest['worker_counts'],
            'task_counts': digest['task_counts'],
            'health_counts': digest['health_counts'],
        },
        message='成功',
    )
