-- 回滚：移除任务健康度表
-- 日期：2026-06-06
-- 对应迁移：migrations/003_add_task_health.sql

PRAGMA foreign_keys = ON;

BEGIN;

DROP INDEX IF EXISTS idx_task_health_workspace_level;
DROP INDEX IF EXISTS idx_task_health_level;
DROP INDEX IF EXISTS idx_task_health_workspace_task;
DROP TABLE IF EXISTS task_health;

COMMIT;
