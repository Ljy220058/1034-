-- 回滚：移除活动数据异常趋势雷达图模型
-- 日期：2026-06-06
-- 对应迁移：migrations/20260606_activity_anomaly_radar_trends.sql
-- 说明：仅删除本迁移新增对象；先删维度子表再删快照父表，确保外键关系可回滚。

PRAGMA foreign_keys = ON;

BEGIN;

DROP INDEX IF EXISTS idx_activity_anomaly_radar_dimensions_key_score;
DROP INDEX IF EXISTS idx_activity_anomaly_radar_dimensions_snapshot_order;
DROP INDEX IF EXISTS idx_activity_anomaly_radar_dimensions_snapshot;
DROP INDEX IF EXISTS idx_activity_anomaly_radar_snapshots_source_platform;
DROP INDEX IF EXISTS idx_activity_anomaly_radar_snapshots_trend_level;
DROP INDEX IF EXISTS idx_activity_anomaly_radar_snapshots_assessed_at;
DROP INDEX IF EXISTS idx_activity_anomaly_radar_snapshots_quality_score;
DROP INDEX IF EXISTS idx_activity_anomaly_radar_snapshots_activity;

DROP TABLE IF EXISTS activity_anomaly_radar_dimensions;
DROP TABLE IF EXISTS activity_anomaly_radar_snapshots;

COMMIT;
