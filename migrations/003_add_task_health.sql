-- 迁移：添加任务健康度表
-- 日期：2026-06-06
-- 回滚：执行 migrations/003_add_task_health.rollback.sql

PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace TEXT NOT NULL,
    task_id TEXT NOT NULL,
    blocked_count INTEGER NOT NULL DEFAULT 0 CHECK (blocked_count >= 0),
    last_failure_reason TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    last_accepted_at TEXT,
    health_level TEXT NOT NULL DEFAULT 'healthy' CHECK (health_level IN ('healthy', 'at_risk', 'blocked', 'failing')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_task_health_workspace_task UNIQUE (workspace, task_id)
);

CREATE INDEX IF NOT EXISTS idx_task_health_workspace_task ON task_health(workspace, task_id);
CREATE INDEX IF NOT EXISTS idx_task_health_level ON task_health(health_level, updated_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_task_health_workspace_level ON task_health(workspace, health_level, updated_at DESC, id DESC);

COMMIT;
