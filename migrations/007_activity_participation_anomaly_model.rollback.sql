-- 回滚：移除活动参与率异常波动数据模型
-- 日期：2026-06-06
-- 对应迁移：migrations/007_activity_participation_anomaly_model.sql
-- 安全说明：仅移除本迁移新增的视图、索引和表；生产环境如需保留历史指标，请先归档 activity_participation_daily_metrics。

PRAGMA foreign_keys = ON;

BEGIN;

DROP VIEW IF EXISTS activity_participation_metric_inputs;

DROP INDEX IF EXISTS idx_activity_participation_metrics_threshold;
DROP INDEX IF EXISTS idx_activity_participation_metrics_anomaly;
DROP INDEX IF EXISTS idx_activity_participation_metrics_group_date;
DROP INDEX IF EXISTS idx_activity_participation_metrics_date_group;
DROP INDEX IF EXISTS idx_activity_participation_metrics_activity_date;
DROP INDEX IF EXISTS idx_activity_participation_thresholds_group;
DROP INDEX IF EXISTS idx_activity_participation_thresholds_activity;
DROP INDEX IF EXISTS idx_activity_participation_thresholds_scope;
DROP INDEX IF EXISTS idx_member_group_memberships_member;
DROP INDEX IF EXISTS idx_member_group_memberships_group;
DROP INDEX IF EXISTS idx_member_groups_group_key;
DROP INDEX IF EXISTS uq_activity_participation_daily_metrics_activity_date_group;

DROP TABLE IF EXISTS activity_participation_daily_metrics;
DROP TABLE IF EXISTS activity_participation_anomaly_thresholds;
DROP TABLE IF EXISTS member_group_memberships;
DROP TABLE IF EXISTS member_groups;

DELETE FROM schema_migrations
WHERE version = 7 AND name = '007_activity_participation_anomaly_model';

COMMIT;
