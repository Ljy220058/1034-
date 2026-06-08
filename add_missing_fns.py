"""Add missing functions that tests import but don't exist."""
from pathlib import Path
PROJECT = Path('/root/autodl-tmp/projects/hermes-swarm-lab')

# 1. Add functions to repository.py
repo_path = PROJECT / 'backend' / 'repository.py'
repo = repo_path.read_text()

new_fn = """

def ensure_workspace_tasks_table() -> None:
    \"\"\"Ensure workspace_tasks and task_health tables exist (for tests).\"\"\"
    from .db import initialize_database as _init_db
    _init_db()


def reset_database() -> None:
    \"\"\"Reset database to clean state (for tests).\"\"\"
    from .database import DB_PATH, init_db as _init
    _init(DB_PATH)
    from .db import initialize_database as _init_ws
    _init_ws()

"""
# Insert after the last import
marker = "\n\n@dataclass\nclass Member:"
if marker in repo:
    repo = repo.replace(marker, new_fn + marker, 1)
    repo_path.write_text(repo)
    print('[OK] repository.py: added ensure_workspace_tasks_table + reset_database')
else:
    print('[WARN] repository.py: insertion point not found')

# 2. Add list_workspace_task_health to worker_board.py
wb_path = PROJECT / 'backend' / 'worker_board.py'
wb = wb_path.read_text()

if 'def list_workspace_task_health' in wb:
    print('[OK] worker_board.py: list_workspace_task_health already exists')
else:
    list_health_fn = """

def list_workspace_task_health(*, workspace_path: str | Path, health_level: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    \"\"\"List task health records, optionally filtered by health level.

    Args:
        workspace_path: Workspace directory path.
        health_level: Optional health level filter.
        limit: Maximum records to return.

    Returns:
        List of task health dicts.
    \"\"\"
    _ensure_schema()
    normalized = _normalize_workspace_path(workspace_path)
    with connect() as connection:
        if health_level:
            rows = connection.execute(
                \"SELECT * FROM task_health WHERE workspace = ? AND health_level = ? ORDER BY updated_at DESC, id DESC LIMIT ?\",
                (normalized, health_level, limit),
            ).fetchall()
        else:
            rows = connection.execute(
                \"SELECT * FROM task_health WHERE workspace = ? ORDER BY updated_at DESC, id DESC LIMIT ?\",
                (normalized, limit),
            ).fetchall()
    return [_row_to_task_health(row) for row in rows]
"""
    # Insert before build_worker_board_snapshot
    marker2 = '\n\ndef build_worker_board_snapshot'
    if marker2 in wb:
        wb = wb.replace(marker2, list_health_fn + marker2, 1)
        wb_path.write_text(wb)
        print('[OK] worker_board.py: added list_workspace_task_health')
    else:
        # Append at end
        wb = wb.rstrip() + list_health_fn + '\n'
        wb_path.write_text(wb)
        print('[OK] worker_board.py: appended list_workspace_task_health')

print('Done')
