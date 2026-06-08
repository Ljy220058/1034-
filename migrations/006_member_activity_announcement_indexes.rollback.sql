-- 回滚：移除成员、活动、公告核心查询索引
-- 日期：2026-06-06
-- 对应迁移：migrations/006_member_activity_announcement_indexes.sql

PRAGMA foreign_keys = ON;

BEGIN;

DROP INDEX IF EXISTS idx_announcements_pinned_created_at;
DROP INDEX IF EXISTS idx_announcements_status_created_at;
DROP INDEX IF EXISTS idx_announcements_created_at;
DROP INDEX IF EXISTS idx_activities_title_start_time;
DROP INDEX IF EXISTS idx_activities_start_time;
DROP INDEX IF EXISTS idx_members_phone;
DROP INDEX IF EXISTS idx_members_role_name;
DROP INDEX IF EXISTS idx_members_name;
DELETE FROM schema_migrations WHERE version = 6 AND name = '006_member_activity_announcement_indexes';

COMMIT;
