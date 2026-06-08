"""Fix baseline test collection errors by adding missing functions."""
from pathlib import Path
PROJECT = Path('/root/autodl-tmp/projects/hermes-swarm-lab')

# === 1. Add to repository.py: list_workspace_task_items, upsert_workspace_task_item, reset_database ===
repo_path = PROJECT / 'backend' / 'repository.py'
repo = repo_path.read_text()

fn_block = '''

def list_workspace_task_items(*, workspace_path, limit=100, status_filter=None, assignee=None):
    """List workspace task items for a given workspace.

    Args:
        workspace_path: Workspace directory path.
        limit: Maximum number of items to return.
        status_filter: Optional task status filter.
        assignee: Optional assignee filter.

    Returns:
        List of WorkspaceTaskItem instances.
    """
    from .task_discovery import list_workspace_tasks as _list
    items = _list(workspace_path, limit=limit, status_filter=status_filter)
    if assignee:
        items = [i for i in items if getattr(i, 'assignee', None) == assignee]
    return items


def upsert_workspace_task_item(*, task_key, title, status, description='', assignee=None, priority=0, metadata=None, workspace_path=None):
    """Create or update a workspace task item.

    Args:
        task_key: Unique task key.
        title: Task title.
        status: Task status.
        description: Task description.
        assignee: Assigned worker.
        priority: Task priority.
        metadata: Additional metadata dict.
        workspace_path: Workspace path (uses default if None).

    Returns:
        Created or updated WorkspaceTaskItem.
    """
    import os
    from pathlib import Path
    from .task_discovery import upsert_workspace_task as _upsert
    from .task_discovery import WorkspaceTask

    if workspace_path is None:
        workspace_path = os.getenv('HERMES_KANBAN_WORKSPACE', str(Path.cwd()))
    if metadata is None:
        metadata = {}

    task = _upsert(
        workspace_path=workspace_path,
        task_key=task_key,
        title=title,
        status=status,
        description=description,
        assignee=assignee,
        priority=priority,
        metadata=metadata,
    )
    # Return a namedtuple-like object
    class _TaskItem:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump(self, mode='python'):
            return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
    return _TaskItem(
        task_key=task.task_key,
        title=task.title,
        status=task.status,
        description=task.description,
        assignee=task.assignee,
        priority=task.priority,
        updated_at=task.updated_at,
        metadata=task.metadata,
    )


def reset_database() -> None:
    """Reset database to clean state (for tests)."""
    from .database import DB_PATH, init_db as _init_db
    _init_db(DB_PATH)

'''

marker = '\n\ndef _row_to_member'
if marker in repo:
    repo = repo.replace(marker, fn_block + marker, 1)
    repo_path.write_text(repo)
    print('[OK] repository.py: added list_workspace_task_items, upsert_workspace_task_item, reset_database')
else:
    print('[WARN] repository.py: marker _row_to_member not found')

# === 2. Add to task_discovery.py: create_task_payloads ===
td_path = PROJECT / 'backend' / 'task_discovery.py'
td = td_path.read_text()

td_fn = '''

def create_task_payloads() -> list[dict]:
    """Create default kanban task payloads for creative task flows.

    Returns:
        List of task payload dicts.
    """
    return [
        {
            'task_key': 'creative-task-001',
            'title': '生成活动创意',
            'status': 'todo',
            'description': '自动生成社群活动创意任务',
            'assignee': None,
            'priority': 5,
        },
        {
            'task_key': 'creative-task-002',
            'title': '审核活动方案',
            'status': 'todo',
            'description': '审核并优化自动生成的活动方案',
            'assignee': None,
            'priority': 4,
        },
    ]

'''

# Insert after the last function
td_marker = '\n\ndef list_workspace_tasks'
if td_marker in td:
    td = td.replace(td_marker, td_fn + td_marker, 1)
    td_path.write_text(td)
    print('[OK] task_discovery.py: added create_task_payloads')
else:
    # Try appending at end
    td = td.rstrip() + td_fn + '\n'
    td_path.write_text(td)
    print('[OK] task_discovery.py: appended create_task_payloads')

# === 3. Add to task_board_models.py: ensure_task_board_schema ===
tbm_path = PROJECT / 'backend' / 'task_board_models.py'
tbm = tbm_path.read_text()

tbm_fn = '''

def ensure_task_board_schema() -> None:
    """Ensure task board and health tables exist (idempotent)."""
    _ensure_board_table()

'''

tbm_marker = '\n\ndef build_task_health_summary'
if tbm_marker in tbm:
    tbm = tbm.replace(tbm_marker, tbm_fn + tbm_marker, 1)
    tbm_path.write_text(tbm)
    print('[OK] task_board_models.py: added ensure_task_board_schema')
else:
    tbm = tbm.rstrip() + tbm_fn + '\n'
    tbm_path.write_text(tbm)
    print('[OK] task_board_models.py: appended ensure_task_board_schema')

print('Done')
