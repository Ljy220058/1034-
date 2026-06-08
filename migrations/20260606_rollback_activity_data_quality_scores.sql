-- 回滚：移除跑步活动数据质量评分模型
-- 日期：2026-06-06
-- 对应迁移：migrations/20260606_activity_data_quality_scores.sql
-- 说明：仅删除本迁移新增对象；先删子表再删父表，确保外键关系可回滚。

PRAGMA foreign_keys = ON;

BEGIN;

DROP INDEX IF EXISTS idx_activity_data_quality_score_reasons_score_order;
DROP INDEX IF EXISTS idx_activity_data_quality_score_reasons_score;
DROP INDEX IF EXISTS idx_activity_data_quality_scores_duplicate_risk;
DROP INDEX IF EXISTS idx_activity_data_quality_scores_quality_score;
DROP INDEX IF EXISTS idx_activity_data_quality_scores_assessed_at;
DROP INDEX IF EXISTS idx_activity_data_quality_scores_source_platform;
DROP INDEX IF EXISTS idx_activity_data_quality_scores_activity;

DROP TABLE IF EXISTS activity_data_quality_score_reasons;
DROP TABLE IF EXISTS activity_data_quality_scores;

COMMIT;
