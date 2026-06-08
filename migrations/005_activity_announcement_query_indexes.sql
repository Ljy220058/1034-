-- 迁移：优化活动相关查询索引并补充活动/公告的时间范围查询支持
-- 日期：2026-06-06
-- 回滚：执行 migrations/005_activity_announcement_query_indexes.rollback.sql

PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_activities_start_time ON activities(start_time DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_registrations_activity_status_member ON registrations(activity_id, status, member_id);
CREATE INDEX IF NOT EXISTS idx_registrations_member_status_activity ON registrations(member_id, status, activity_id);
CREATE INDEX IF NOT EXISTS idx_attendances_activity_status_member ON attendances(activity_id, status, member_id);
CREATE INDEX IF NOT EXISTS idx_attendances_member_status_activity ON attendances(member_id, status, activity_id);
CREATE INDEX IF NOT EXISTS idx_attendances_signed_in_at ON attendances(signed_in_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_announcements_created_at ON announcements(created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_announcements_status_created_at ON announcements(status, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_announcements_pinned_created_at ON announcements(is_pinned DESC, created_at DESC, id DESC);

CREATE VIEW IF NOT EXISTS activity_participation_facts AS
SELECT
    r.activity_id,
    r.member_id,
    date(a.start_time) AS activity_date,
    r.status AS registration_status,
    att.status AS attendance_status,
    CASE
        WHEN r.status = 'cancelled' THEN 'cancelled'
        WHEN att.status = 'signed_in' THEN 'signed_in'
        WHEN att.status = 'absent' THEN 'absent'
        ELSE 'registered_unchecked'
    END AS participation_status,
    att.signed_in_at,
    att.gps_checked,
    r.created_at AS registered_at,
    a.start_time AS activity_start_time
FROM registrations r
JOIN activities a ON a.id = r.activity_id
LEFT JOIN attendances att
    ON att.activity_id = r.activity_id
   AND att.member_id = r.member_id;

INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (5, '005_activity_announcement_query_indexes');

COMMIT;
