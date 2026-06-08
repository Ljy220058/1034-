-- 回滚：移除活动报名候补队列数据结构
-- 日期：2026-06-06
-- 正向迁移：执行 migrations/20260606_activity_waitlist_contract.sql

PRAGMA foreign_keys = ON;

BEGIN;

DROP INDEX IF EXISTS idx_activity_waitlist_entries_promoted_registration;
DROP INDEX IF EXISTS idx_activity_waitlist_entries_offer_expires_at;
DROP INDEX IF EXISTS idx_activity_waitlist_entries_member_status;
DROP INDEX IF EXISTS idx_activity_waitlist_entries_activity_status_position;
DROP INDEX IF EXISTS uq_activity_waitlist_entries_activity_position_active;
DROP INDEX IF EXISTS uq_activity_waitlist_entries_activity_member_active;
DROP TABLE IF EXISTS activity_waitlist_entries;

DELETE FROM schema_migrations WHERE version = 2026060601 AND name = '20260606_activity_waitlist_contract';

COMMIT;
