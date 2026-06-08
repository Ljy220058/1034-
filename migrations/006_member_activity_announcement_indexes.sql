-- 迁移：补充成员、活动、公告核心查询索引
-- 日期：2026-06-06
-- 回滚：执行 migrations/006_member_activity_announcement_indexes.rollback.sql

PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_members_name ON members(name COLLATE NOCASE, id ASC);
CREATE INDEX IF NOT EXISTS idx_members_role_name ON members(role, name COLLATE NOCASE, id ASC);
CREATE INDEX IF NOT EXISTS idx_members_phone ON members(phone) WHERE phone IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_activities_start_time ON activities(start_time DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_activities_title_start_time ON activities(title COLLATE NOCASE, start_time DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_announcements_created_at ON announcements(created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_announcements_status_created_at ON announcements(status, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_announcements_pinned_created_at ON announcements(is_pinned DESC, created_at DESC, id DESC);

INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (6, '006_member_activity_announcement_indexes');

COMMIT;
