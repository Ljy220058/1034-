from __future__ import annotations

import os
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_DB_PATH = Path(os.getenv('RUNNING_CLUB_DB_PATH') or (Path(tempfile.gettempdir()) / 'running_club.db'))
DB_PATH = Path(os.getenv('RUNNING_CLUB_DB_PATH') or DEFAULT_DB_PATH)

SCHEMA_SQL = '''
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT UNIQUE,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('leader', 'admin', 'member')),
    running_years INTEGER NOT NULL DEFAULT 0 CHECK (running_years >= 0),
    pace TEXT,
    usual_distance_km REAL CHECK (usual_distance_km IS NULL OR usual_distance_km >= 0),
    training_goal TEXT,
    password_hash TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    start_time TEXT NOT NULL,
    location TEXT NOT NULL,
    route TEXT,
    distance_km REAL CHECK (distance_km IS NULL OR distance_km >= 0),
    pace_group TEXT,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'registered' CHECK (status IN ('registered', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(activity_id, member_id),
    FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE,
    FOREIGN KEY(member_id) REFERENCES members(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attendances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'signed_in' CHECK (status IN ('signed_in', 'absent')),
    signed_in_at TEXT NOT NULL,
    gps_checked INTEGER NOT NULL DEFAULT 0 CHECK (gps_checked IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(activity_id, member_id),
    FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE,
    FOREIGN KEY(member_id) REFERENCES members(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
    is_pinned INTEGER NOT NULL DEFAULT 0 CHECK (is_pinned IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_queue_workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'disabled')),
    capabilities TEXT,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
'''


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path or DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON;')
    return connection


@contextmanager
def connect(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    connection = get_connection(db_path)
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db(db_path: Path | None = None) -> None:
    global DB_PATH
    if db_path is not None:
        DB_PATH = Path(db_path)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect(DB_PATH) as connection:
        connection.executescript(SCHEMA_SQL)
