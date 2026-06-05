from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models import ApiResponse, WorkerIntakeCreate, WorkerIntakeOut, WorkspaceTaskOut
from ..repository import create_task_queue_worker, list_task_queue_workers
from ..task_discovery import list_workspace_tasks
from .common import CurrentUser, get_current_user

router = APIRouter(prefix='/api/v1/workspaces', tags=['workspaces'])

VALID_TASK_STATUSES = {'todo', 'running', 'done', 'blocked', 'ready', 'archived'}


def _resolve_workspace_selector(selector: str | None) -> str:
    if selector is None or selector == 'current':
        return str(Path.cwd())
    if selector.startswith('workspace:'):
        return selector.removeprefix('workspace:')
    raise HTTPException(status_code=422, detail='invalid workspace selector')


def _normalize_workspace_path(workspace_path: str) -> str:
    path = Path(unquote(workspace_path)).expanduser()
    try:
        return str(path.resolve(strict=False))
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=422, detail='invalid workspace path') from exc


@router.get('/tasks', response_model=ApiResponse)
def read_workspace_tasks(
    current_user: CurrentUser = Depends(get_current_user),
    workspace: str | None = Query(default=None, min_length=1, max_length=120),
    workspace_path: str | None = Query(default=None, min_length=1, max_length=500),
    status: str | None = Query(default=None, min_length=1, max_length=40),
    limit: int | None = Query(default=None, ge=1, le=100),
) -> ApiResponse:
    _ = current_user
    selector = workspace_path or workspace
    if status is not None and status not in VALID_TASK_STATUSES:
        raise HTTPException(status_code=422, detail='invalid task status filter')
    if workspace_path is None and selector is not None and selector not in {'current'} and not selector.startswith('workspace:'):
        raise HTTPException(status_code=422, detail='invalid workspace selector')
    effective_workspace = _normalize_workspace_path(workspace_path or _resolve_workspace_selector(selector))
    tasks = list_workspace_tasks(effective_workspace, limit=limit or 100, status_filter=status)
    return ApiResponse(data=[task.model_dump(mode='json') for task in tasks])


@router.post('/task-queue/workers/intake', response_model=ApiResponse, status_code=201)
def intake_task_queue_worker(
    payload: WorkerIntakeCreate,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    if current_user.role not in {'admin', 'leader'}:
        raise HTTPException(status_code=403, detail='forbidden')
    worker, _ = create_task_queue_worker(
        payload.worker_key,
        payload.name,
        payload.status,
        payload.capabilities,
    )
    return ApiResponse(data=WorkerIntakeOut(**worker).model_dump(mode='json'))


@router.post('/task-queue/workers/intake', response_model=ApiResponse, status_code=201)
def intake_task_queue_worker(
    payload: WorkerIntakeCreate,
    current_user: CurrentUser = Depends(get_current_user),
) -> ApiResponse:
    if current_user.role not in {'admin', 'leader'}:
        raise HTTPException(status_code=403, detail='forbidden')
    worker, _ = create_task_queue_worker(
        payload.worker_key,
        payload.name,
        payload.status,
        payload.capabilities,
    )
    return ApiResponse(data=WorkerIntakeOut(**worker).model_dump(mode='json'))
