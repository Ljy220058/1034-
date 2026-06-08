-- 回滚：删除活动数据质量评分模型
-- 日期：2026-06-06
-- 正向迁移：20260606_001_activity_quality_scoring.sql

BEGIN;

DROP TABLE IF EXISTS activity_quality_scores;

COMMIT;
