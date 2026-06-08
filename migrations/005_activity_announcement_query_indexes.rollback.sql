-- 回滚：移除活动与公告查询索引
-- 日期：2026-06-06
-- 对应迁移：migrations/005_activity_announcement_query_indexes.sql

PRAGMA foreign_keys = ON;

BEGIN;

DROP VIEW IF EXISTS activity_participation_facts;
DROP INDEX IF EXISTS idx_announcements_pinned_created_at;
DROP INDEX IF EXISTS idx_announcements_status_created_at;
DROP INDEX IF EXISTS idx_announcements_created_at;
DROP INDEX IF EXISTS idx_attendances_signed_in_at;
DROP INDEX IF EXISTS idx_attendances_member_status_activity;
DROP INDEX IF EXISTS idx_attendances_activity_status_member;
DROP INDEX IF EXISTS idx_registrations_member_status_activity;
DROP INDEX IF EXISTS idx_registrations_activity_status_member;
DROP INDEX IF EXISTS idx_activities_start_time;
DELETE FROM schema_migrations WHERE version = 5 AND name = '005_activity_announcement_query_indexes';

COMMIT;
