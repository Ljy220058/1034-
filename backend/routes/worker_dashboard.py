from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, Query

from ..models import ApiResponse
from ..repository import list_task_queue_workers
from ..task_board_models import list_task_health_rows
from ..worker_board import build_worker_board_snapshot
from ..worker_recommendations import recommend_worker_for_task
from .common import CurrentUser, get_current_user

router = APIRouter(prefix='/api/v1/dashboard', tags=['dashboard'])


def _normalize_status_counts(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count values for a dictionary field.

    Args:
        items: Source items.
        field: Field name to count.

    Returns:
        Status count mapping.
    """
    counter = Counter(str(item.get(field, 'unknown')) for item in items)
    return dict(counter)


def _normalize_workspace_path(workspace_path: str) -> str:
    """Normalize a workspace path from the request.

    Args:
        workspace_path: Raw workspace path.

    Returns:
        Normalized workspace path.

    Raises:
        ValueError: If the path is empty.
    """
    normalized = workspace_path.strip()
    if not normalized:
        raise ValueError('workspace_path is required')
    return normalized


def _snapshot_payload(workspace_path: str, include_health: bool, limit: int) -> dict[str, Any]:
    """Build the dashboard digest payload.

    Args:
        workspace_path: Workspace root path.
        include_health: Whether to include task health rows.
        limit: Maximum number of task health rows.

    Returns:
        Serialized dashboard digest payload.
    """
    normalized_workspace = _normalize_workspace_path(workspace_path)
    workers = list_task_queue_workers()
    health_rows_raw = list_task_health_rows(normalized_workspace) if include_health else []
    health_rows: list[dict[str, Any]] = []
    for row in health_rows_raw[:limit]:
        if hasattr(row, 'model_dump'):
            health_rows.append(row.model_dump(mode='json'))
        else:
            health_rows.append(dict(row))
    worker_counts = _normalize_status_counts(workers, 'status')
    health_counts = _normalize_status_counts(health_rows, 'health_level')
    snapshot = build_worker_board_snapshot(normalized_workspace).model_dump(mode='json')
    recommendations: list[dict[str, Any]] = []
    for item in snapshot['recent_tasks'][:limit]:
        metadata = item.get('metadata', {}) if isinstance(item.get('metadata'), dict) else {}
        capabilities_value = metadata.get('capabilities', [])
        capabilities = [str(value) for value in capabilities_value] if isinstance(capabilities_value, list) else None
        recommendation = recommend_worker_for_task(
            str(item.get('title', '')),
            str(item.get('description', '')),
            capabilities=capabilities,
        )
        recommendations.append({
            'task_key': item.get('task_key'),
            'title': item.get('title'),
            'recommended_lane': recommendation['recommended_lane'],
            'reason': recommendation['reason'],
            'source': item.get('source', 'workspace_tasks'),
            'status': item.get('status'),
        })
    return {
        'workspace_path': normalized_workspace,
        'summary': {
            'workers_total': len(workers),
            'workers_active': worker_counts.get('active', 0),
            'workers_running': worker_counts.get('running', 0),
            'task_health_total': len(health_rows),
            'blocked_tasks': health_counts.get('blocked', 0),
            'failing_tasks': health_counts.get('failing', 0),
        },
        'workers': {
            'items': workers,
            'status_counts': worker_counts,
        },
        'task_health': {
            'items': health_rows,
            'health_counts': health_counts,
        },
        'snapshot': snapshot,
        'recommendations': recommendations,
    }

def _build_idle_summary(workspace_path: str) -> dict[str, Any]:
    """Build an idle worker summary for dispatch recommendations.

    Args:
        workspace_path: Workspace root path.

    Returns:
        Dict with summary and dispatch_recommendations keys.
    """
    payload = _snapshot_payload(workspace_path, include_health=True, limit=20)
    return {
        "summary": payload["summary"],
        "dispatch_recommendations": payload["recommendations"],
    }



@router.get('/digest', response_model=ApiResponse)
def read_dashboard_digest(
    current_user: CurrentUser = Depends(get_current_user),
    workspace_path: str = Query(min_length=1, max_length=500),
    health_level: str | None = Query(default=None, min_length=1, max_length=40),
    limit: int = Query(default=20, ge=1, le=100),
) -> ApiResponse:
    """Read the dashboard digest.

    Args:
        current_user: Authenticated user.
        workspace_path: Workspace root path.
        health_level: Optional health level filter.
        limit: Maximum number of health rows.

    Returns:
        Structured API response with board summary data.
    """
    _ = current_user
    payload = _snapshot_payload(workspace_path, True, limit)
    if health_level:
        normalized_level = health_level.strip().lower()
        payload['task_health']['items'] = [
            row
            for row in payload['task_health']['items']
            if str(row.get('health_level') or '').lower() == normalized_level
        ]
    return ApiResponse(data=payload, message='成功')


@router.get('/digest/summary', response_model=ApiResponse)
def read_dashboard_summary(
    current_user: CurrentUser = Depends(get_current_user),
    workspace_path: str = Query(min_length=1, max_length=500),
) -> ApiResponse:
    """Return a compact dashboard summary for the front end.

    Args:
        current_user: Authenticated user.
        workspace_path: Workspace root path.

    Returns:
        Structured API response with summary, worker and recommendation snippets.
    """
    _ = current_user
    payload = _snapshot_payload(workspace_path, True, limit=10)
    data = {
        'workspace_path': payload['workspace_path'],
        'summary': payload['summary'],
        'workers': payload['workers']['items'][:3],
        'task_health': payload['task_health']['items'][:5],
        'recommendations': payload['recommendations'][:3],
        'snapshot': payload['snapshot'],
    }
    return ApiResponse(data=data, message='已返回看板摘要')
