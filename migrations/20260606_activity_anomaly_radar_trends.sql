-- 迁移：添加活动数据异常趋势雷达图模型
-- 日期：2026-06-06
-- 回滚：执行 migrations/20260606_rollback_activity_anomaly_radar_trends.sql
-- 说明：
-- 1. activity_anomaly_radar_snapshots 保存每次活动面向雷达图的趋势快照元数据与可复用 0-100 总分。
-- 2. activity_anomaly_radar_dimensions 保存前端雷达图维度数组：维度键、中文标签、0-100 分值、趋势方向与排序。
-- 3. 本模型复用 activity_data_quality_scores 的原始质量评分/异常结果，不重复保存扣分原因；重点服务“趋势维度与可视化输出契约”。

PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE IF NOT EXISTS activity_anomaly_radar_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    quality_score_id INTEGER,
    radar_version TEXT NOT NULL DEFAULT 'activity-anomaly-radar-v1',
    source_platform TEXT NOT NULL DEFAULT 'unknown'
        CHECK (source_platform IN ('coros', 'garmin', 'generic', 'manual_file', 'csv', 'json', 'manual', 'unknown')),
    source_record_id TEXT,
    anomaly_trend_score INTEGER NOT NULL DEFAULT 0 CHECK (anomaly_trend_score BETWEEN 0 AND 100),
    trend_level TEXT NOT NULL DEFAULT 'normal'
        CHECK (trend_level IN ('normal', 'watch', 'warning', 'critical')),
    dimension_count INTEGER NOT NULL DEFAULT 5 CHECK (dimension_count > 0),
    baseline_window_days INTEGER NOT NULL DEFAULT 30 CHECK (baseline_window_days > 0),
    radar_payload_json TEXT NOT NULL DEFAULT '{}',
    assessed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_activity_anomaly_radar_snapshots_activity_version UNIQUE (activity_id, radar_version),
    CONSTRAINT fk_activity_anomaly_radar_snapshots_activity
        FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
    CONSTRAINT fk_activity_anomaly_radar_snapshots_quality_score
        FOREIGN KEY (quality_score_id) REFERENCES activity_data_quality_scores(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS activity_anomaly_radar_dimensions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    radar_snapshot_id INTEGER NOT NULL,
    dimension_key TEXT NOT NULL
        CHECK (dimension_key IN ('pace_shift', 'distance_outlier', 'duplicate_upload', 'gps_sparse', 'source_platform')),
    label_zh TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0 CHECK (score BETWEEN 0 AND 100),
    severity TEXT NOT NULL DEFAULT 'normal'
        CHECK (severity IN ('normal', 'watch', 'warning', 'critical')),
    trend_direction TEXT NOT NULL DEFAULT 'flat'
        CHECK (trend_direction IN ('up', 'down', 'flat', 'unknown')),
    baseline_value REAL,
    observed_value REAL,
    unit TEXT,
    display_order INTEGER NOT NULL DEFAULT 0 CHECK (display_order >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_activity_anomaly_radar_dimensions_snapshot_key UNIQUE (radar_snapshot_id, dimension_key),
    CONSTRAINT fk_activity_anomaly_radar_dimensions_snapshot
        FOREIGN KEY (radar_snapshot_id) REFERENCES activity_anomaly_radar_snapshots(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_activity_anomaly_radar_snapshots_activity
    ON activity_anomaly_radar_snapshots(activity_id);

CREATE INDEX IF NOT EXISTS idx_activity_anomaly_radar_snapshots_quality_score
    ON activity_anomaly_radar_snapshots(quality_score_id);

CREATE INDEX IF NOT EXISTS idx_activity_anomaly_radar_snapshots_assessed_at
    ON activity_anomaly_radar_snapshots(assessed_at);

CREATE INDEX IF NOT EXISTS idx_activity_anomaly_radar_snapshots_trend_level
    ON activity_anomaly_radar_snapshots(trend_level);

CREATE INDEX IF NOT EXISTS idx_activity_anomaly_radar_snapshots_source_platform
    ON activity_anomaly_radar_snapshots(source_platform);

CREATE INDEX IF NOT EXISTS idx_activity_anomaly_radar_dimensions_snapshot
    ON activity_anomaly_radar_dimensions(radar_snapshot_id);

CREATE INDEX IF NOT EXISTS idx_activity_anomaly_radar_dimensions_snapshot_order
    ON activity_anomaly_radar_dimensions(radar_snapshot_id, display_order);

CREATE INDEX IF NOT EXISTS idx_activity_anomaly_radar_dimensions_key_score
    ON activity_anomaly_radar_dimensions(dimension_key, score);

COMMIT;
