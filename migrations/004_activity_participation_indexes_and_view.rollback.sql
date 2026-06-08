-- 回滚：移除活动参与率分析索引与状态视图
-- 日期：2026-06-06
-- 对应迁移：migrations/004_activity_participation_indexes_and_view.sql

PRAGMA foreign_keys = ON;

BEGIN;

DROP VIEW IF EXISTS activity_participation_facts;
DROP INDEX IF EXISTS idx_announcements_created_at;
DROP INDEX IF EXISTS idx_attendances_signed_in_at;
DROP INDEX IF EXISTS idx_attendances_member_status_activity;
DROP INDEX IF EXISTS idx_attendances_activity_status_member;
DROP INDEX IF EXISTS idx_registrations_member_status_activity;
DROP INDEX IF EXISTS idx_registrations_activity_status_member;
DROP INDEX IF EXISTS idx_activities_start_time;
DELETE FROM schema_migrations WHERE version = 4 AND name = '004_activity_participation_indexes_and_view';

COMMIT;
