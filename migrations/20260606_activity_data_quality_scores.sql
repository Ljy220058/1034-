-- 迁移：添加跑步活动数据质量评分模型
-- 日期：2026-06-06
-- 回滚：执行 migrations/20260606_rollback_activity_data_quality_scores.sql
-- 说明：
-- 1. activity_data_quality_scores 保存每次活动质量评分的原始输入、0-100 总分与前端中文说明。
-- 2. activity_data_quality_score_reasons 保存可展示/可排序的扣分或加分明细，避免把结构化原因塞进单个文本字段。
-- 3. 覆盖来源平台：高驰(coros)、佳明(garmin)、CSV(csv)、JSON(json)，并保留 manual/unknown 兜底。

PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE IF NOT EXISTS activity_data_quality_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    source_platform TEXT NOT NULL DEFAULT 'unknown'
        CHECK (source_platform IN ('coros', 'garmin', 'csv', 'json', 'manual', 'unknown')),
    source_record_id TEXT,
    scoring_version TEXT NOT NULL DEFAULT 'activity-quality-v1',
    distance_km REAL NOT NULL CHECK (distance_km >= 0),
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds > 0),
    pace_seconds_per_km INTEGER NOT NULL CHECK (pace_seconds_per_km > 0),
    gps_point_count INTEGER NOT NULL DEFAULT 0 CHECK (gps_point_count >= 0),
    duplicate_risk_score INTEGER NOT NULL DEFAULT 0 CHECK (duplicate_risk_score BETWEEN 0 AND 100),
    quality_score INTEGER NOT NULL CHECK (quality_score BETWEEN 0 AND 100),
    quality_level TEXT NOT NULL DEFAULT 'unknown'
        CHECK (quality_level IN ('excellent', 'good', 'fair', 'poor', 'unknown')),
    explanation_zh TEXT NOT NULL,
    raw_payload_json TEXT,
    assessed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_activity_data_quality_scores_activity_version UNIQUE (activity_id, scoring_version),
    CONSTRAINT fk_activity_data_quality_scores_activity
        FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS activity_data_quality_score_reasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quality_score_id INTEGER NOT NULL,
    reason_code TEXT NOT NULL,
    reason_type TEXT NOT NULL CHECK (reason_type IN ('bonus', 'penalty', 'info')),
    impact_points INTEGER NOT NULL DEFAULT 0 CHECK (impact_points BETWEEN -100 AND 100),
    message_zh TEXT NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0 CHECK (display_order >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_activity_data_quality_score_reasons_score_code UNIQUE (quality_score_id, reason_code),
    CONSTRAINT fk_activity_data_quality_score_reasons_score
        FOREIGN KEY (quality_score_id) REFERENCES activity_data_quality_scores(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_activity_data_quality_scores_activity
    ON activity_data_quality_scores(activity_id);

CREATE INDEX IF NOT EXISTS idx_activity_data_quality_scores_source_platform
    ON activity_data_quality_scores(source_platform);

CREATE INDEX IF NOT EXISTS idx_activity_data_quality_scores_assessed_at
    ON activity_data_quality_scores(assessed_at);

CREATE INDEX IF NOT EXISTS idx_activity_data_quality_scores_quality_score
    ON activity_data_quality_scores(quality_score);

CREATE INDEX IF NOT EXISTS idx_activity_data_quality_scores_duplicate_risk
    ON activity_data_quality_scores(duplicate_risk_score);

CREATE INDEX IF NOT EXISTS idx_activity_data_quality_score_reasons_score
    ON activity_data_quality_score_reasons(quality_score_id);

CREATE INDEX IF NOT EXISTS idx_activity_data_quality_score_reasons_score_order
    ON activity_data_quality_score_reasons(quality_score_id, display_order);

COMMIT;
