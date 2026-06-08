-- 迁移：添加活动参与率异常波动数据模型
-- 日期：2026-06-06
-- 回滚：执行 migrations/007_activity_participation_anomaly_model.rollback.sql
-- 说明：
--   1. member_groups/member_group_memberships 用于按成员分组统计参与率；
--   2. activity_participation_anomaly_thresholds 保存异常波动判定阈值；
--   3. activity_participation_daily_metrics 保存按活动、日期、成员分组聚合后的参与率指标；
--   4. activity_participation_metric_inputs 视图提供后端计算指标表所需的明细输入。

PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS member_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_key TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_member_groups_group_key UNIQUE (group_key)
);

CREATE TABLE IF NOT EXISTS member_group_memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    valid_from TEXT NOT NULL DEFAULT (date('now')),
    valid_to TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_member_group_memberships_group_member_from UNIQUE (group_id, member_id, valid_from),
    CHECK (valid_to IS NULL OR valid_to >= valid_from),
    FOREIGN KEY (group_id) REFERENCES member_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS activity_participation_anomaly_thresholds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope_type TEXT NOT NULL DEFAULT 'global' CHECK (scope_type IN ('global', 'activity', 'member_group')),
    activity_id INTEGER,
    group_id INTEGER,
    baseline_window_days INTEGER NOT NULL DEFAULT 30 CHECK (baseline_window_days > 0),
    min_sample_activities INTEGER NOT NULL DEFAULT 3 CHECK (min_sample_activities > 0),
    warning_drop_pp REAL NOT NULL DEFAULT 15.0 CHECK (warning_drop_pp >= 0),
    critical_drop_pp REAL NOT NULL DEFAULT 30.0 CHECK (critical_drop_pp >= warning_drop_pp),
    warning_z_score REAL NOT NULL DEFAULT -1.5 CHECK (warning_z_score <= 0),
    critical_z_score REAL NOT NULL DEFAULT -2.5 CHECK (critical_z_score <= warning_z_score),
    min_participation_rate REAL NOT NULL DEFAULT 0.5 CHECK (min_participation_rate >= 0 AND min_participation_rate <= 1),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (scope_type = 'global' AND activity_id IS NULL AND group_id IS NULL)
        OR (scope_type = 'activity' AND activity_id IS NOT NULL AND group_id IS NULL)
        OR (scope_type = 'member_group' AND activity_id IS NULL AND group_id IS NOT NULL)
    ),
    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES member_groups(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS activity_participation_daily_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    metric_date TEXT NOT NULL,
    group_id INTEGER,
    registered_count INTEGER NOT NULL DEFAULT 0 CHECK (registered_count >= 0),
    signed_in_count INTEGER NOT NULL DEFAULT 0 CHECK (signed_in_count >= 0),
    absent_count INTEGER NOT NULL DEFAULT 0 CHECK (absent_count >= 0),
    cancelled_count INTEGER NOT NULL DEFAULT 0 CHECK (cancelled_count >= 0),
    participation_rate REAL NOT NULL DEFAULT 0 CHECK (participation_rate >= 0 AND participation_rate <= 1),
    baseline_participation_rate REAL CHECK (baseline_participation_rate IS NULL OR (baseline_participation_rate >= 0 AND baseline_participation_rate <= 1)),
    rate_delta_pp REAL,
    z_score REAL,
    anomaly_level TEXT NOT NULL DEFAULT 'insufficient_data' CHECK (anomaly_level IN ('normal', 'warning', 'critical', 'insufficient_data')),
    threshold_id INTEGER,
    calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (signed_in_count <= registered_count),
    CHECK (absent_count <= registered_count),
    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES member_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (threshold_id) REFERENCES activity_participation_anomaly_thresholds(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_activity_participation_daily_metrics_activity_date_group
ON activity_participation_daily_metrics(activity_id, metric_date, COALESCE(group_id, 0));

CREATE INDEX IF NOT EXISTS idx_member_groups_group_key ON member_groups(group_key);
CREATE INDEX IF NOT EXISTS idx_member_group_memberships_group ON member_group_memberships(group_id, member_id);
CREATE INDEX IF NOT EXISTS idx_member_group_memberships_member ON member_group_memberships(member_id, group_id);
CREATE INDEX IF NOT EXISTS idx_activity_participation_thresholds_scope ON activity_participation_anomaly_thresholds(scope_type, is_active);
CREATE INDEX IF NOT EXISTS idx_activity_participation_thresholds_activity ON activity_participation_anomaly_thresholds(activity_id) WHERE activity_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_activity_participation_thresholds_group ON activity_participation_anomaly_thresholds(group_id) WHERE group_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_activity_participation_metrics_activity_date ON activity_participation_daily_metrics(activity_id, metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_activity_participation_metrics_date_group ON activity_participation_daily_metrics(metric_date DESC, group_id);
CREATE INDEX IF NOT EXISTS idx_activity_participation_metrics_group_date ON activity_participation_daily_metrics(group_id, metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_activity_participation_metrics_anomaly ON activity_participation_daily_metrics(anomaly_level, metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_activity_participation_metrics_threshold ON activity_participation_daily_metrics(threshold_id) WHERE threshold_id IS NOT NULL;

CREATE VIEW IF NOT EXISTS activity_participation_metric_inputs AS
SELECT
    a.id AS activity_id,
    date(a.start_time) AS metric_date,
    NULL AS group_id,
    r.member_id,
    r.status AS registration_status,
    att.status AS attendance_status,
    CASE WHEN att.status = 'signed_in' THEN 1 ELSE 0 END AS is_signed_in,
    CASE WHEN att.status = 'absent' THEN 1 ELSE 0 END AS is_absent,
    CASE WHEN r.status = 'cancelled' THEN 1 ELSE 0 END AS is_cancelled,
    a.start_time AS activity_start_time,
    r.created_at AS registered_at,
    att.signed_in_at
FROM activities a
JOIN registrations r ON r.activity_id = a.id
LEFT JOIN attendances att
    ON att.activity_id = r.activity_id
   AND att.member_id = r.member_id
UNION ALL
SELECT
    a.id AS activity_id,
    date(a.start_time) AS metric_date,
    mgm.group_id,
    r.member_id,
    r.status AS registration_status,
    att.status AS attendance_status,
    CASE WHEN att.status = 'signed_in' THEN 1 ELSE 0 END AS is_signed_in,
    CASE WHEN att.status = 'absent' THEN 1 ELSE 0 END AS is_absent,
    CASE WHEN r.status = 'cancelled' THEN 1 ELSE 0 END AS is_cancelled,
    a.start_time AS activity_start_time,
    r.created_at AS registered_at,
    att.signed_in_at
FROM activities a
JOIN registrations r ON r.activity_id = a.id
JOIN member_group_memberships mgm
    ON mgm.member_id = r.member_id
   AND date(a.start_time) >= mgm.valid_from
   AND (mgm.valid_to IS NULL OR date(a.start_time) <= mgm.valid_to)
LEFT JOIN attendances att
    ON att.activity_id = r.activity_id
   AND att.member_id = r.member_id;

INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES (7, '007_activity_participation_anomaly_model');

COMMIT;
