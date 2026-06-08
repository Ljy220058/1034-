from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..models import ApiResponse, WorkerIntakeCreate, WorkerIntakeOut
from ..worker_digest import build_worker_digest_payload, default_worker_digest_workspace
from ..worker_priority_router import route_task_to_worker
from ..worker_recommendations import QueueWorker, build_worker_board, list_queue_workers, upsert_queue_worker

router = APIRouter(prefix='/api/v1/workers', tags=['workers'])


class PriorityRouteRequest(BaseModel):
    """Priority routing request payload.

    Attributes:
        task_key: Stable task key.
        title: Task title.
        description: Optional task description.
        priority: Task priority used as a tie breaker.
        workspace_path: Workspace path for reading current board load.
    """

    task_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=2000)
    priority: int = Field(default=0, ge=0, le=999)
    workspace_path: str = Field(min_length=1, max_length=500)


TASK_TYPE_ROLE_RULES: dict[str, dict[str, str]] = {
    'backend': {'后端': 'backend', 'API': 'backend', 'FastAPI': 'backend', 'SQLite': 'backend', '数据库': 'backend'},
    'frontend': {'前端': 'frontend', '页面': 'frontend', 'UI': 'frontend', 'React': 'frontend', 'Vue': 'frontend'},
    'test': {'测试': 'test', 'pytest': 'test', '单测': 'test', '回归': 'test', '验证': 'qa'},
    'review': {'评审': 'review', 'review': 'review', '审查': 'review', '重构': 'review', '安全': 'review'},
    'qa': {'验收': 'qa', '联调': 'qa', '手测': 'qa', '冒烟': 'qa', '检查': 'qa'},
}


def _decide_role(title: str, description: str) -> tuple[str, list[str]]:
    """Infer a task type from title and description.

    Args:
        title: Task title.
        description: Task description.

    Returns:
        Tuple of role name and matching reasons.
    """
    content = f'{title}\n{description}'
    reasons: list[str] = []
    role_hits: dict[str, int] = {role: 0 for role in TASK_TYPE_ROLE_RULES}
    for role, keyword_map in TASK_TYPE_ROLE_RULES.items():
        for keyword, mapped_role in keyword_map.items():
            if keyword.lower() in content.lower():
                role_hits[role] += 1
                reasons.append(f'命中关键词「{keyword}」→ {mapped_role}')
    if not reasons:
        return 'backend', ['未命中明确关键词，默认分配给后端 worker']
    best_role = max(role_hits.items(), key=lambda item: (item[1], item[0]))[0]
    return best_role, reasons


def _score_worker(task_role: str, worker: QueueWorker, preferred_worker: str | None) -> tuple[int, list[str]]:
    """Score a worker for a task role.

    Args:
        task_role: Inferred task role.
        worker: Worker row.
        preferred_worker: Optional preferred worker key.

    Returns:
        Score and human readable reasons.
    """
    score = 0
    reasons: list[str] = []
    if worker.status == 'active':
        score += 50
        reasons.append('worker 处于 active 状态')
    elif worker.status == 'paused':
        score += 10
        reasons.append('worker 处于 paused 状态，可作为兜底')
    else:
        score -= 40
        reasons.append('worker 非活跃状态')

    capability_blob = ' '.join(worker.capabilities + [worker.name]).lower()
    role_keywords = {
        'backend': ('backend', 'api', 'fastapi', 'sqlite', 'db', 'database', '服务端'),
        'frontend': ('frontend', 'ui', 'react', 'vue', 'html', 'css', '页面'),
        'test': ('test', 'pytest', 'qa', '验证', '测试'),
        'review': ('review', '审查', '评审', 'security', 'quality'),
        'qa': ('qa', '验收', '联调', '冒烟', '检查'),
    }.get(task_role, ())
    matched = [keyword for keyword in role_keywords if keyword.lower() in capability_blob]
    if matched:
        score += 20 + len(matched) * 5
        reasons.append(f'能力命中 {", ".join(matched[:4])}')

    if preferred_worker and worker.worker_key == preferred_worker:
        score += 30
        reasons.append('命中用户指定的 preferred_worker')

    return score, reasons


@router.post('/intake', response_model=ApiResponse)
def intake_worker(payload: WorkerIntakeCreate) -> ApiResponse:
    """Create or update a worker intake record.

    Args:
        payload: Worker intake request payload.

    Returns:
        Structured API response with worker intake details.
    """
    worker, action = upsert_queue_worker(payload.worker_key, payload.name, payload.status, payload.capabilities)
    return ApiResponse(data=WorkerIntakeOut(**worker.model_dump()).model_dump(mode='json'), message='已创建 worker' if action == 'created' else '已更新 worker')


@router.get('/intake', response_model=ApiResponse)
def list_workers() -> ApiResponse:
    """List known workers.

    Returns:
        Structured API response with worker list.
    """
    workers = [WorkerIntakeOut(**worker.model_dump()).model_dump(mode='json') for worker in list_queue_workers()]
    return ApiResponse(data=workers, message='成功')


@router.post('/allocate', response_model=ApiResponse)
def allocate_worker(
    title: str = Query(min_length=1, max_length=200),
    description: str = Query(default='', max_length=2000),
    preferred_worker: str | None = Query(default=None, max_length=120),
) -> ApiResponse:
    """Select the best worker for a creative task.

    Args:
        title: Task title.
        description: Task description.
        preferred_worker: Optional preferred worker key.

    Returns:
        Structured API response with candidate selection and reason.

    Raises:
        HTTPException: When no worker can be selected.
    """
    task_role, reasons = _decide_role(title, description)
    workers = list_queue_workers()
    if not workers:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='暂无可用 worker')

    scored_workers: list[dict[str, object]] = []
    for worker in workers:
        score, score_reasons = _score_worker(task_role, worker, preferred_worker)
        scored_workers.append(
            {
                'worker_key': worker.worker_key,
                'name': worker.name,
                'status': worker.status,
                'capabilities': worker.capabilities,
                'score': score,
                'reasons': score_reasons,
            }
        )

    scored_workers.sort(key=lambda item: (-int(item['score']), str(item['status']) != 'active', str(item['name']), str(item['worker_key'])))
    chosen = scored_workers[0]
    data = {
        'task_type': task_role,
        'title': title.strip(),
        'workspace_path': None,
        'assignee': chosen['worker_key'],
        'workspace': None,
        'candidate_count': len(scored_workers),
        'candidates': scored_workers[:5],
        'reason': '；'.join(reasons + [f"优先选择 {chosen['worker_key']}"]),
    }
    return ApiResponse(data=data, message='已完成 worker 分流')


@router.post('/priority-router', response_model=ApiResponse)
def route_worker_by_priority(payload: PriorityRouteRequest) -> ApiResponse:
    """Route a task to the best worker by task type and current load.

    Args:
        payload: Priority routing request.

    Returns:
        Structured API response with selected worker, candidates, and decision log.

    Raises:
        HTTPException: No active worker is available.
    """
    routed = route_task_to_worker(
        workspace_path=payload.workspace_path,
        task_key=payload.task_key,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
    )
    if routed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='暂无可分配的 active worker')
    return ApiResponse(data=routed.payload, message='已完成优先级分配')


@router.get('/digest', response_model=ApiResponse)
def read_worker_digest(workspace_path: str | None = None, include_health: bool = True) -> ApiResponse:
    """Return an aggregate Chinese worker dashboard digest.

    Args:
        workspace_path: Optional workspace path filter.

    Returns:
        Structured API response with digest summary.
    """
    normalized = default_worker_digest_workspace(workspace_path)
    return ApiResponse(data=build_worker_digest_payload(normalized, include_health=include_health), message='成功')


@router.get('/summary', response_model=ApiResponse)
def read_worker_summary(workspace_path: str | None = None) -> ApiResponse:
    """Return a compact worker dashboard summary.

    Args:
        workspace_path: Optional workspace path filter.

    Returns:
        Structured API response with summary fields.
    """
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


@router.get('/alerts', response_model=ApiResponse)
def read_worker_alerts(workspace_path: str | None = None) -> ApiResponse:
    """Return repeated warning rows for the worker dashboard.

    Args:
        workspace_path: Optional workspace path filter.

    Returns:
        Structured API response with warning rows.
    """
    normalized = default_worker_digest_workspace(workspace_path)
    digest = build_worker_digest_payload(normalized)
    alerts = digest['alerts']
    return ApiResponse(data={'workspace_path': normalized, 'summary': {'total': len(alerts)}, 'alerts': alerts}, message='成功')


@router.get('/health', response_model=ApiResponse)
def read_worker_health(workspace_path: str | None = None) -> ApiResponse:
    """Return task health rows for a workspace.

    Args:
        workspace_path: Optional workspace path filter.

    Returns:
        Structured API response with task health rows.
    """
    normalized = default_worker_digest_workspace(workspace_path)
    _ensure_digest_schema()
    return ApiResponse(data=_list_health_rows(normalized, limit=100), message='成功')


@router.get('/board', response_model=ApiResponse)
def read_worker_board(workspace_path: str | None = None) -> ApiResponse:
    """Return a worker board snapshot for a workspace.

    Args:
        workspace_path: Workspace root path.

    Returns:
        Structured API response with the worker board snapshot.
    """
    normalized = default_worker_digest_workspace(workspace_path)
    snapshot = build_worker_board(normalized)
    return ApiResponse(data=snapshot, message='成功')


def _public_worker(worker: dict[str, object]) -> dict[str, object]:
    """构造可返回给调度者的 worker 摘要。"""
    return {
        'worker_key': worker.get('worker_key'),
        'name': worker.get('name'),
        'status': worker.get('status'),
        'capabilities': list(worker.get('capabilities') or []),
        'last_seen_at': worker.get('last_seen_at'),
    }


def _task_label(task: dict[str, object]) -> str:
    """拼接任务标题、描述和元数据文本。"""
    metadata = task.get('metadata') if isinstance(task.get('metadata'), dict) else {}
    return ' '.join(str(value) for value in (task.get('title'), task.get('description'), metadata.get('description')) if value)


def _recommended_task_type(worker: dict[str, object], tasks: list[dict[str, object]]) -> tuple[str, str | None]:
    """根据 worker 能力和待派发任务推断推荐任务类型。"""
    text = ' '.join(str(item) for item in list(worker.get('capabilities') or []) + [worker.get('name'), worker.get('worker_key')]).lower()
    task_text = ' '.join(_task_label(task).lower() for task in tasks)
    if any(keyword in text for keyword in ('pytest', 'qa', 'quality', 'review', '验收', '测试', '评审')):
        return '测试验收类任务', '优先处理 pytest、质量门禁、回归验证或接口验收任务。'
    if any(keyword in text for keyword in ('frontend', 'ui', 'html', 'css', '页面', '前端')):
        return '前端页面类任务', '优先处理页面联调、静态资源或可视化展示任务。'
    if any(keyword in text for keyword in ('fastapi', 'sqlite', 'backend', 'api', '后端', '数据库')):
        return '后端接口类任务', '优先处理 FastAPI、SQLite、结构化错误返回或只读汇总接口。'
    if any(keyword in task_text for keyword in ('测试', 'pytest', '验收', 'review', '质量')):
        return '测试验收类任务', '当前待派发任务偏测试验收，可作为低风险补位。'
    return '通用整理类任务', '优先处理轻量汇总、任务梳理或低风险只读接口。'


def _ready_tasks(board: dict[str, object]) -> list[dict[str, object]]:
    """读取看板中待派发任务，不修改任何任务状态。"""
    tasks = board.get('recent_changes') or board.get('recent_tasks') or []
    return [task for task in tasks if isinstance(task, dict) and str(task.get('status')) in {'todo', 'ready'}]


def _build_idle_dispatch_payload(workspace_path: str) -> dict[str, object]:
    """生成空闲 worker 中文智能派发提示。"""
    board = build_worker_board(workspace_path)
    summary = board.get('summary', {}) if isinstance(board.get('summary'), dict) else {}
    tasks = [task for task in (board.get('recent_changes') or board.get('recent_tasks') or []) if isinstance(task, dict)]
    running_assignees = {str(task.get('assignee')) for task in tasks if task.get('assignee') and str(task.get('status')) in {'running', 'doing'}}
    all_workers = [worker for worker in board.get('idle_workers', []) + board.get('busy_workers', []) if isinstance(worker, dict)]
    idle_workers = [
        worker
        for worker in all_workers
        if str(worker.get('status')) == 'active'
        and str(worker.get('worker_key')) not in running_assignees
        and str(worker.get('name')) not in running_assignees
    ]
    busy_workers = [worker for worker in all_workers if worker not in idle_workers]
    ready_tasks = [task for task in tasks if str(task.get('status')) in {'todo', 'ready'}]
    prompts: list[dict[str, object]] = []
    for worker in idle_workers[:10]:
        task_type, reason = _recommended_task_type(worker, ready_tasks)
        key = str(worker.get('worker_key') or worker.get('name') or '')
        prompts.append({
            **_public_worker(worker),
            'recommended_task_type': task_type,
            'reason': reason,
            '中文提示': f'{key} 当前空闲，适合接收新任务；推荐派发「{task_type}」。{reason}',
        })
    if not idle_workers or not ready_tasks:
        advice = '当前没有空闲 worker 或待派发任务，请先补充 worker intake 或新任务。'
    else:
        advice = f'建议优先派发 {len(prompts)} 个空闲 worker，先处理 {len(ready_tasks)} 个待办/ready 任务。'
    return {
        'workspace_path': workspace_path,
        'summary': {
            'idle_worker_count': len(idle_workers),
            'busy_worker_count': len(busy_workers),
            'ready_task_count': len(ready_tasks),
            'running_task_count': int(summary.get('running') or 0),
            'blocked_task_count': int(summary.get('blocked') or 0),
        },
        'next_step_advice': advice,
        'idle_workers': [_public_worker(worker) for worker in idle_workers[:10]],
        'dispatch_prompts': prompts,
    }


@router.get('/idle-dispatch-prompts', response_model=ApiResponse)
def read_idle_dispatch_prompts(workspace_path: str | None = None) -> ApiResponse:
    """返回空闲 worker 中文智能派发提示。

    Args:
        workspace_path: 可选工作区路径；不传时使用项目默认工作区。

    Returns:
        只读中文派发建议，不改变任何任务状态。
    """
    normalized = default_worker_digest_workspace(workspace_path)
    return ApiResponse(data=_build_idle_dispatch_payload(normalized), message='已生成空闲 worker 智能派发提示')

