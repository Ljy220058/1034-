-- 迁移：增加活动数据质量评分模型
-- 日期：2026-06-06
-- 回滚：执行对应 rollback 脚本恢复为未评分版本

BEGIN;

CREATE TABLE IF NOT EXISTS activity_quality_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    distance_km REAL NOT NULL CHECK (distance_km >= 0),
    pace_minutes_per_km REAL NOT NULL CHECK (pace_minutes_per_km > 0),
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    gps_points_count INTEGER NOT NULL DEFAULT 0 CHECK (gps_points_count >= 0),
    source_platform TEXT NOT NULL CHECK (source_platform IN ('huawei', 'garmin', 'csv', 'json', 'manual', 'other')),
    duplicate_risk REAL NOT NULL DEFAULT 0 CHECK (duplicate_risk >= 0 AND duplicate_risk <= 1),
    quality_score INTEGER NOT NULL CHECK (quality_score BETWEEN 0 AND 100),
    quality_explanation_zh TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE,
    UNIQUE(activity_id)
);

CREATE INDEX IF NOT EXISTS idx_activity_quality_scores_activity_id ON activity_quality_scores(activity_id);
CREATE INDEX IF NOT EXISTS idx_activity_quality_scores_quality_score ON activity_quality_scores(quality_score);
CREATE INDEX IF NOT EXISTS idx_activity_quality_scores_source_platform ON activity_quality_scores(source_platform);

COMMIT;
