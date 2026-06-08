from __future__ import annotations

from pathlib import Path

from . import database


def get_settings():
    from .settings import get_settings as _get_settings

    return _get_settings()


def initialize_database(settings=None) -> None:
    if settings is None:
        db_path = database.DB_PATH
    else:
        db_path = Path(getattr(settings, 'database_path', database.DB_PATH))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    database.DB_PATH = db_path
    database.init_db(db_path)
    with database.connect(db_path) as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS workspace_task_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace TEXT NOT NULL,
                task_key TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('todo', 'ready', 'running', 'blocked', 'done', 'archived')),
                assignee TEXT,
                priority INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT NOT NULL DEFAULT '{}',
                task_id TEXT,
                parent_task_id TEXT,
                UNIQUE(workspace, task_key)
            )
            ''')

        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS workspace_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace TEXT NOT NULL,
                task_key TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('todo', 'ready', 'running', 'blocked', 'done', 'archived')),
                assignee TEXT,
                priority INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT NOT NULL DEFAULT '{}',
                task_id TEXT,
                parent_task_id TEXT,
                UNIQUE(workspace, task_key)
            )
            '''
        )
