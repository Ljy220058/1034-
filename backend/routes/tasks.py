from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..models import ApiResponse

router = APIRouter(prefix='/api/v1/tasks', tags=['tasks'])


@dataclass(frozen=True)
class TaskProgressItem:
    """任务进度条目。"""

    task_id: int
    title: str
    status: str
    owner: str
    progress_percent: int
    completed_steps: list[str]
    remaining_steps: list[str]

    def model_dump(self) -> dict[str, Any]:
        """序列化为 JSON 兼容字典。"""
        return {
            'task_id': self.task_id,
            'title': self.title,
            'status': self.status,
            'owner': self.owner,
            'progress': {
                'percent': self.progress_percent,
                'completed_steps': self.completed_steps,
                'remaining_steps': self.remaining_steps,
            },
        }


@dataclass(frozen=True)
class TaskMetadataItem:
    """轻量任务元数据条目。"""

    task_id: int
    summary: str
    status: str
    labels: list[str]
    updated_at: datetime

    def model_dump(self) -> dict[str, Any]:
        """序列化为 JSON 兼容字典。"""
        return {
            'task_id': self.task_id,
            'summary': self.summary,
            'status': self.status,
            'labels': self.labels,
            'updated_at': self.updated_at.astimezone(timezone.utc).isoformat(),
        }


class ProgressSimulationRequest(BaseModel):
    """任务进度模拟请求。"""

    task_id: int = Field(gt=0)
    steps: int = Field(default=3, ge=2, le=10)


_TASKS: list[TaskProgressItem] = [
    TaskProgressItem(
        task_id=1,
        title='补充任务列表接口测试',
        status='todo',
        owner='backend-dev',
        progress_percent=10,
        completed_steps=['需求分析'],
        remaining_steps=['补充测试用例', '实现接口', '跑通校验'],
    ),
    TaskProgressItem(
        task_id=2,
        title='中文创意：后端任务流状态接口',
        status='running',
        owner='backend-dev',
        progress_percent=65,
        completed_steps=['已完成列表查询', '已完成详情接口'],
        remaining_steps=['补齐回归测试', '联调接口', '手动验证'],
    ),
    TaskProgressItem(
        task_id=3,
        title='任务进度模拟推送',
        status='done',
        owner='backend-dev',
        progress_percent=100,
        completed_steps=['设计接口', '实现接口', '补充测试'],
        remaining_steps=[],
    ),
]

_TASK_METADATA: list[TaskMetadataItem] = [
    TaskMetadataItem(
        task_id=101,
        summary='补齐任务卡片的摘要字段，方便前端预览面板直接展示。',
        status='running',
        labels=['backend', 'api', 'preview'],
        updated_at=datetime(2026, 6, 6, 20, 30, tzinfo=timezone.utc),
    ),
    TaskMetadataItem(
        task_id=102,
        summary='整理任务标签与更新时间，供自动化流程和看板同步使用。',
        status='ready',
        labels=['backend', 'automation'],
        updated_at=datetime(2026, 6, 6, 21, 5, tzinfo=timezone.utc),
    ),
    TaskMetadataItem(
        task_id=103,
        summary='补充轻量任务元数据接口测试，确保结构化返回稳定。',
        status='done',
        labels=['test', 'api'],
        updated_at=datetime(2026, 6, 6, 21, 40, tzinfo=timezone.utc),
    ),
]


def _get_task(task_id: int) -> TaskProgressItem:
    """按 ID 查找任务。"""
    for item in _TASKS:
        if item.task_id == task_id:
            return item
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='任务不存在')


def _build_timeline(task_id: int, steps: int) -> list[dict[str, int]]:
    """构造模拟进度时间线。"""
    if steps == 2:
        percents = [0, 100]
    else:
        gap = 100 // (steps - 1)
        percents = [min(100, index * gap) for index in range(steps - 1)] + [100]
        percents[0] = 0
        percents[-1] = 100
    return [{'task_id': task_id, 'step': index + 1, 'percent': percent} for index, percent in enumerate(percents)]


def _list_task_metadata() -> list[dict[str, Any]]:
    """返回轻量任务元数据列表。"""
    return [item.model_dump() for item in sorted(_TASK_METADATA, key=lambda item: (-item.updated_at.timestamp(), item.task_id))]


@router.get('/progress', response_model=ApiResponse)
def list_task_progress() -> ApiResponse:
    """返回任务流状态列表。"""
    items = [item.model_dump() for item in _TASKS]
    return ApiResponse(data={'count': len(items), 'items': items}, message='成功')


@router.get('/progress/{task_id}', response_model=ApiResponse)
def read_task_progress(task_id: int) -> ApiResponse:
    """返回单条任务状态详情。"""
    task = _get_task(task_id)
    return ApiResponse(data=task.model_dump(), message='成功')


@router.get('/metadata', response_model=ApiResponse)
def list_task_metadata() -> ApiResponse:
    """返回任务摘要、状态、标签与更新时间。"""
    metadata = _list_task_metadata()
    return ApiResponse(data={'count': len(metadata), 'items': metadata}, message='成功')


@router.get('/metadata/{task_id}', response_model=ApiResponse)
def read_task_metadata(task_id: int) -> ApiResponse:
    """返回单条任务轻量元数据。"""
    for item in _TASK_METADATA:
        if item.task_id == task_id:
            return ApiResponse(data=item.model_dump(), message='成功')
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='任务不存在')


@router.post('/progress/simulate', response_model=ApiResponse)
def simulate_task_progress(payload: ProgressSimulationRequest) -> ApiResponse:
    """模拟任务进度推进。"""
    _get_task(payload.task_id)
    return ApiResponse(
        data={
            'task_id': payload.task_id,
            'steps': payload.steps,
            'timeline': _build_timeline(payload.task_id, payload.steps),
        },
        message='成功',
    )
