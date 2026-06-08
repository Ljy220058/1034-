from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..models import ApiResponse
from ..task_import import batch_import_task_metadata
from ..worker_board import build_worker_board
from .common import CurrentUser, admin_or_leader, get_current_user

router = APIRouter(prefix='/api/v1', tags=['task-imports'])
DEFAULT_WORKSPACE_PATH = '/root/autodl-tmp/projects/hermes-swarm-lab'


class TaskImportItem(BaseModel):
    """任务导入条目。"""

    task_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    status: str = Field(default='todo', min_length=1, max_length=40)
    assignee: str | None = Field(default=None, max_length=120)
    priority: int = Field(default=0, ge=0, lt=1000)
    workspace_path: str | None = Field(default=None, max_length=500)

    model_config = {'extra': 'forbid'}


class TaskImportRequest(BaseModel):
    """任务批量导入请求。"""

    items: list[TaskImportItem] = Field(default_factory=list)

    model_config = {'extra': 'forbid'}


@router.post('/tasks/items/import', response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def import_task_items(
    payload: TaskImportRequest,
    current_user: CurrentUser = Depends(get_current_user),
    workspace_path: str = Query(default=DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500),
) -> ApiResponse:
    """批量导入任务条目并写入工作区任务表。"""
    admin_or_leader(current_user)
    if len(payload.items) != 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='创意任务必须正好两张')
    try:
        result = batch_import_task_metadata([item.model_dump() for item in payload.items], workspace_path=workspace_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ApiResponse(data=result.model_dump(mode='json'), message='成功')


@router.get('/workspaces/board', response_model=ApiResponse)
def read_import_workspace_board(
    current_user: CurrentUser = Depends(get_current_user),
    workspace_path: str = Query(default=DEFAULT_WORKSPACE_PATH, min_length=1, max_length=500),
) -> ApiResponse:
    """读取导入任务所在工作区看板。"""
    admin_or_leader(current_user)
    board = build_worker_board(workspace_path, refresh=False)
    tasks = board.get('recent_changes', [])
    return ApiResponse(data={'workspace_path': board.get('workspace_path', workspace_path), 'tasks': tasks}, message='成功')
