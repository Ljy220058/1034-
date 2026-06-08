-- 回滚：移除跑团成员活跃度分层模型
-- 日期：2026-06-06
-- 对应迁移：migrations/20260606_member_activity_segments.sql
-- 说明：仅删除本迁移新增对象；先删子表再删规则表，确保外键关系可回滚。

PRAGMA foreign_keys = ON;

BEGIN;

DROP INDEX IF EXISTS idx_member_activity_segment_rules_active_order;
DROP INDEX IF EXISTS idx_member_activity_segments_last_active;
DROP INDEX IF EXISTS idx_member_activity_segments_segment_computed;
DROP INDEX IF EXISTS idx_member_activity_segments_member_computed;
DROP INDEX IF EXISTS idx_member_activity_segments_window;
DROP INDEX IF EXISTS idx_member_activity_segments_segment_code;
DROP INDEX IF EXISTS idx_member_activity_segments_member;

DROP TABLE IF EXISTS member_activity_segments;
DROP TABLE IF EXISTS member_activity_segment_rules;

COMMIT;
