-- 迁移：添加跑团成员活跃度分层模型
-- 日期：2026-06-06
-- 回滚：执行 migrations/20260606_rollback_member_activity_segments.sql
-- 说明：
-- 1. member_activity_segments 保存按成员、统计窗口、算法版本生成的活跃度指标快照与分层结果。
-- 2. member_activity_segment_rules 保存可配置的分层展示与运营动作元数据，便于首页推荐、运营周报、召回提醒复用同一套中文标签。
-- 3. 指标来源来自 members、activities、registrations、attendances 的离线/定时计算结果；本迁移不写应用层计算逻辑。

PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE IF NOT EXISTS member_activity_segment_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_code TEXT NOT NULL,
    segment_label_zh TEXT NOT NULL,
    color_hex TEXT NOT NULL DEFAULT '#64748B'
        CHECK (length(color_hex) = 7 AND substr(color_hex, 1, 1) = '#'),
    display_order INTEGER NOT NULL DEFAULT 0 CHECK (display_order >= 0),
    recommendation_weight INTEGER NOT NULL DEFAULT 0 CHECK (recommendation_weight BETWEEN -100 AND 100),
    weekly_report_priority INTEGER NOT NULL DEFAULT 0 CHECK (weekly_report_priority >= 0),
    recall_priority INTEGER NOT NULL DEFAULT 0 CHECK (recall_priority >= 0),
    rule_description_zh TEXT NOT NULL,
    operation_action_zh TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_member_activity_segment_rules_code UNIQUE (segment_code),
    CHECK (segment_code IN ('new_member', 'stable_active', 'at_risk', 'silent', 'core_pacer'))
);

CREATE TABLE IF NOT EXISTS member_activity_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    segment_code TEXT NOT NULL,
    scoring_version TEXT NOT NULL DEFAULT 'member-activity-v1',
    metric_start_date TEXT NOT NULL,
    metric_end_date TEXT NOT NULL,
    running_distance_7d_km REAL NOT NULL DEFAULT 0 CHECK (running_distance_7d_km >= 0),
    running_distance_30d_km REAL NOT NULL DEFAULT 0 CHECK (running_distance_30d_km >= 0),
    registration_count_30d INTEGER NOT NULL DEFAULT 0 CHECK (registration_count_30d >= 0),
    checkin_count_30d INTEGER NOT NULL DEFAULT 0 CHECK (checkin_count_30d >= 0),
    activity_completion_rate REAL NOT NULL DEFAULT 0 CHECK (activity_completion_rate BETWEEN 0 AND 1),
    consecutive_absence_count INTEGER NOT NULL DEFAULT 0 CHECK (consecutive_absence_count >= 0),
    last_active_at TEXT,
    computed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_member_activity_segments_member_version_window
        UNIQUE (member_id, scoring_version, metric_start_date, metric_end_date),
    CONSTRAINT fk_member_activity_segments_member
        FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
    CONSTRAINT fk_member_activity_segments_rule
        FOREIGN KEY (segment_code) REFERENCES member_activity_segment_rules(segment_code) ON UPDATE CASCADE,
    CHECK (date(metric_start_date) IS NOT NULL),
    CHECK (date(metric_end_date) IS NOT NULL),
    CHECK (date(metric_start_date) <= date(metric_end_date)),
    CHECK (last_active_at IS NULL OR datetime(last_active_at) IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_member_activity_segments_member
    ON member_activity_segments(member_id);

CREATE INDEX IF NOT EXISTS idx_member_activity_segments_segment_code
    ON member_activity_segments(segment_code);

CREATE INDEX IF NOT EXISTS idx_member_activity_segments_window
    ON member_activity_segments(metric_start_date, metric_end_date);

CREATE INDEX IF NOT EXISTS idx_member_activity_segments_member_computed
    ON member_activity_segments(member_id, computed_at DESC);

CREATE INDEX IF NOT EXISTS idx_member_activity_segments_segment_computed
    ON member_activity_segments(segment_code, computed_at DESC);

CREATE INDEX IF NOT EXISTS idx_member_activity_segments_last_active
    ON member_activity_segments(last_active_at);

CREATE INDEX IF NOT EXISTS idx_member_activity_segment_rules_active_order
    ON member_activity_segment_rules(is_active, display_order);

INSERT OR IGNORE INTO member_activity_segment_rules (
    segment_code,
    segment_label_zh,
    color_hex,
    display_order,
    recommendation_weight,
    weekly_report_priority,
    recall_priority,
    rule_description_zh,
    operation_action_zh
) VALUES
    (
        'new_member',
        '新成员',
        '#38BDF8',
        10,
        20,
        30,
        20,
        '入团 30 天内，近 30 天签到少于 3 次且未达到稳定活跃标准。',
        '首页推荐新手友好活动；运营周报关注首月转化；提醒管理员进行欢迎和路线答疑。'
    ),
    (
        'stable_active',
        '稳定活跃',
        '#22C55E',
        20,
        60,
        60,
        10,
        '近 30 天签到不少于 3 次，完成率不低于 60%，且连续缺席少于 2 次。',
        '首页推荐常规训练和进阶活动；周报展示为健康活跃基本盘；保持轻触达。'
    ),
    (
        'at_risk',
        '潜在流失',
        '#F59E0B',
        30,
        10,
        80,
        80,
        '近 30 天仍有报名或签到痕迹，但连续缺席达到 2 次，或最近活跃距今 14-29 天。',
        '活动召回提醒优先推送低门槛活动；周报列入需关怀名单；可发送个性化问候。'
    ),
    (
        'silent',
        '已沉默',
        '#94A3B8',
        40,
        -20,
        90,
        100,
        '最近活跃距今不少于 30 天，或近 30 天报名和签到均为 0。',
        '首页减少高强度推荐；召回提醒使用轻量活动、福利或问卷；周报追踪沉默人数变化。'
    ),
    (
        'core_pacer',
        '核心带跑者',
        '#8B5CF6',
        50,
        100,
        100,
        0,
        '角色为 leader/admin，或近 30 天签到不少于 8 次、跑量不少于 80km、完成率不低于 80%。',
        '首页优先推荐带队/配速任务；周报突出贡献；邀请担任活动领队或训练计划共创者。'
    );

COMMIT;
