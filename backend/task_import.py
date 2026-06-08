from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .database import connect, init_db
    from .repository import upsert_workspace_task_item
    from .workspace_validation import validate_workspace_access_path
except ImportError:  # pragma: no cover - fallback for direct module loading in tests
    from backend.database import connect, init_db
    from backend.repository import upsert_workspace_task_item
    from backend.workspace_validation import validate_workspace_access_path

TASK_IMPORT_STATUSES = {'todo', 'running', 'done'}
TASK_IMPORT_LEGACY_RUNNING_STATUS = 'doing'
TASK_IMPORT_PRIORITY_RANGE = range(0, 1000)
TASK_IMPORT_STATUS_ALIASES = {
    TASK_IMPORT_LEGACY_RUNNING_STATUS: 'running',
}


def _normalize_import_status(status: str) -> str:
    """Normalize imported task status to workspace storage format.

    Args:
        status: Raw imported task status.

    Returns:
        Workspace-compatible task status.
    """
    return normalize_task_import_status(status)


@dataclass(frozen=True)
class ImportedTaskMetadata:
    """Normalized batch-imported task metadata.

    Attributes:
        task_key: Unique task key.
        title: Task title.
        status: Task status.
        description: Task description.
        assignee: Optional assignee.
        priority: Task priority.
        workspace_path: Optional workspace path.
        updated_at: Optional persisted update timestamp.
        metadata: Optional persisted task metadata.
    """

    task_key: str
    title: str
    status: str
    description: str
    assignee: str | None
    priority: int
    workspace_path: str | None
    updated_at: str | None = None
    metadata: dict[str, Any] | None = None

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        """Serialize the imported task metadata.

        Args:
            mode: Serialization mode, kept for compatibility.

        Returns:
            JSON-ready dictionary.
        """
        payload: dict[str, Any] = {
            'task_key': self.task_key,
            'title': self.title,
            'status': self.status,
            'description': self.description,
            'assignee': self.assignee,
            'priority': self.priority,
            'workspace_path': self.workspace_path,
        }
        if self.updated_at is not None:
            payload['updated_at'] = self.updated_at
        if self.metadata is not None:
            payload['metadata'] = self.metadata
        return payload


@dataclass(frozen=True)
class BatchImportResult:
    """Batch import result payload.

    Attributes:
        count: Number of imported tasks.
        items: Imported task metadata items.
    """

    count: int
    items: list[ImportedTaskMetadata]

    def model_dump(self, mode: str = 'python') -> dict[str, Any]:
        """Serialize the batch import result.

        Args:
            mode: Serialization mode, kept for compatibility.

        Returns:
            JSON-ready dictionary.
        """
        return {'count': self.count, 'items': [item.model_dump(mode=mode) for item in self.items]}


def _normalize_workspace_path(workspace_path: str | Path | None) -> str | None:
    """Normalize and validate a workspace path.

    Args:
        workspace_path: Raw workspace path.

    Returns:
        Normalized workspace path or None.

    Raises:
        ValueError: If the workspace path is invalid.
    """
    if workspace_path is None:
        return None
    return validate_workspace_access_path(workspace_path)


def normalize_task_import_status(status: str) -> str:
    """Normalize imported task status for workspace persistence.

    Args:
        status: Raw imported task status.

    Returns:
        Workspace-compatible task status.
    """
    return TASK_IMPORT_STATUS_ALIASES.get(status, status)


def _validate_task_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload.get('task_key'), str) or not payload['task_key'].strip():
        raise ValueError('invalid task key')
    if not isinstance(payload.get('title'), str) or not payload['title'].strip():
        raise ValueError('invalid title')
    if not isinstance(payload.get('description'), str) or not payload['description'].strip():
        raise ValueError('invalid description')
    status = payload.get('status', 'todo')
    status = _normalize_import_status(status) if isinstance(status, str) else status
    if status not in TASK_IMPORT_STATUSES:
        raise ValueError('任务状态不合法')
    priority = payload.get('priority', 0)
    if not isinstance(priority, int) or priority not in TASK_IMPORT_PRIORITY_RANGE:
        raise ValueError('invalid priority')
    assignee = payload.get('assignee')
    if assignee is not None and (not isinstance(assignee, str) or not assignee.strip()):
        raise ValueError('负责人不存在')
    workspace_path = payload.get('workspace_path')
    if workspace_path is not None and not isinstance(workspace_path, str):
        raise ValueError('invalid workspace path')


def _validate_assignee_exists(assignee: str | None) -> None:
    if not assignee:
        raise ValueError('负责人不存在')
    with connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM task_queue_workers WHERE (name = ? OR worker_key = ?) AND status IN (?, ?)",
            (assignee, assignee, 'active', 'paused'),
        ).fetchone()
    if row is None:
        row = connection.execute(
            "SELECT 1 FROM task_queue_workers WHERE (name = ? OR worker_key = ?) AND status = ?",
            (assignee, assignee, 'disabled'),
        ).fetchone()
        if row is None:
            raise ValueError('负责人不存在')


def _persist_imported_task(item: ImportedTaskMetadata) -> ImportedTaskMetadata:
    """Persist a normalized imported task into workspace_tasks.

    Args:
        item: Validated imported task metadata.

    Returns:
        Imported task metadata enriched with persisted fields.

    Raises:
        ValueError: Workspace path is missing or persistence fails.
    """
    if item.workspace_path is None:
        raise ValueError('workspace_path 不能为空')
    metadata = {'description': item.description, 'workspace_path': item.workspace_path}
    persisted = upsert_workspace_task_item(
        workspace_path=item.workspace_path,
        task_key=item.task_key,
        title=item.title,
        status=item.status,
        description=item.description,
        assignee=item.assignee,
        priority=item.priority,
        metadata=metadata,
    )
    if not persisted or persisted.get('task_key') != item.task_key:
        raise ValueError('任务导入失败')
    return ImportedTaskMetadata(
        task_key=str(persisted.get('task_key', item.task_key)),
        title=str(persisted.get('title', item.title)),
        status=str(persisted.get('status', item.status)),
        description=str((persisted.get('metadata', {}) or {}).get('description', item.description)),
        assignee=persisted.get('assignee', item.assignee),
        priority=int(persisted.get('priority', item.priority)),
        workspace_path=str(persisted.get('workspace_path', item.workspace_path)),
        updated_at=str(persisted.get('updated_at')) if persisted.get('updated_at') is not None else None,
        metadata=(persisted.get('metadata') if isinstance(persisted.get('metadata'), dict) else metadata),
    )


def batch_import_task_metadata(items: list[dict[str, Any]], *, workspace_path: str | Path | None = None) -> BatchImportResult:
    """Import a batch of task metadata records.

    Args:
        items: Batch import records.
        workspace_path: Optional workspace path to attach to each record.

    Returns:
        Batch import result containing imported metadata.

    Raises:
        ValueError: If payload validation fails.
    """
    if not items:
        raise ValueError('items 不能为空')
    normalized_workspace_path = _normalize_workspace_path(workspace_path)
    imported: list[ImportedTaskMetadata] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f'第{index}项任务数据格式不正确')
        _validate_task_payload(item)
        assignee = item.get('assignee')
        if isinstance(assignee, str):
            _validate_assignee_exists(assignee.strip())
        imported.append(
            ImportedTaskMetadata(
                task_key=item['task_key'].strip(),
                title=item['title'].strip(),
                status=_normalize_import_status(item.get('status', 'todo')),
                description=item['description'].strip(),
                assignee=assignee.strip() if isinstance(assignee, str) else None,
                priority=item.get('priority', 0),
                workspace_path=_normalize_workspace_path(item.get('workspace_path')) or normalized_workspace_path,
            )
        )
    imported = [_persist_imported_task(item) for item in imported]
    return BatchImportResult(count=len(imported), items=imported)


def ensure_task_import_schema() -> None:
    """Ensure the import subsystem can access the database.

    Returns:
        None.
    """
    init_db()
