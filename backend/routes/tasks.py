from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..models import ApiResponse, WorkerIntakeCreate
from ..repository import create_task_queue_worker, list_task_queue_workers
from ..task_discovery import list_workspace_tasks, create_task_payloads
from .common import CurrentUser, admin_or_leader, get_current_user

router = APIRouter(prefix='/api/v1', tags=['tasks'])


@router.post('/task-queue/workers/intake', response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def intake_worker(payload: WorkerIntakeCreate, current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    worker, _ = create_task_queue_worker(payload.worker_key, payload.name, payload.status, payload.capabilities)
    return ApiResponse(data={
        'id': worker['id'],
        'worker_key': worker['worker_key'],
        'name': worker['name'],
        'status': worker['status'],
        'capabilities': eval(worker['capabilities']) if isinstance(worker.get('capabilities'), str) else worker['capabilities'],
        'last_seen_at': worker['last_seen_at'],
        'created_at': worker['created_at'],
        'updated_at': worker['updated_at'],
    })


@router.get('/task-queue/workers', response_model=ApiResponse)
def read_workers(current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    return ApiResponse(data=list_task_queue_workers())


@router.post('/tasks/workspace-scoped-creation-helper')
def workspace_scoped_creation_helper() -> dict[str, object]:
    return {'count': 2, 'tasks': create_task_payloads()}


@router.get('/workspaces/tasks', response_model=ApiResponse)
def read_workspace_tasks(workspace_path: str, limit: int = 100, status_filter: str | None = Query(default=None, alias='status'), current_user: CurrentUser = Depends(get_current_user)) -> ApiResponse:
    admin_or_leader(current_user)
    try:
        tasks = list_workspace_tasks(workspace_path, limit=limit, status_filter=status_filter)
    except ValueError as exc:
        message = str(exc)
        if message == 'invalid task status filter':
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='invalid workspace path') from exc
    return ApiResponse(data=[task.model_dump(mode='json') for task in tasks])
