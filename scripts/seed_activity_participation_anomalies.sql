-- 种子数据：活动参与率异常波动本地演示数据
-- 日期：2026-06-06
-- 前置：先执行 migrations/007_activity_participation_anomaly_model.sql
-- 覆盖：全局阈值、成员分组阈值、正常/预警/严重/样本不足四类指标

PRAGMA foreign_keys = ON;

BEGIN;

INSERT OR IGNORE INTO members (
    id, name, phone, role, running_years, pace, usual_distance_km, training_goal, password_hash
) VALUES
    (9101, '异常波动领队', '15551910001', 'leader', 8, '5:00/km', 15.0, '维护活动质量', 'seeded-anomaly-leader'),
    (9102, '新人组跑友A', '15551910002', 'member', 1, '6:30/km', 5.0, '稳定参加晨跑', 'seeded-anomaly-a'),
    (9103, '新人组跑友B', '15551910003', 'member', 1, '6:45/km', 5.0, '提升耐力', 'seeded-anomaly-b'),
    (9104, '进阶组跑友C', '15551910004', 'member', 4, '5:30/km', 10.0, '准备半马', 'seeded-anomaly-c'),
    (9105, '进阶组跑友D', '15551910005', 'member', 5, '5:20/km', 12.0, '保持训练节奏', 'seeded-anomaly-d');

INSERT OR IGNORE INTO activities (
    id, title, start_time, location, route, distance_km, pace_group, description
) VALUES
    (9101, '异常波动基线晨跑一', '2026-05-20T07:00:00+00:00', '世纪公园', '湖边 5km', 5.0, 'easy', '用于参与率基线的历史活动。'),
    (9102, '异常波动基线晨跑二', '2026-05-27T07:00:00+00:00', '世纪公园', '湖边 5km', 5.0, 'easy', '用于参与率基线的历史活动。'),
    (9103, '异常波动预警晨跑', '2026-06-03T07:00:00+00:00', '世纪公园', '湖边 5km', 5.0, 'easy', '参与率较基线下降，触发 warning。'),
    (9104, '异常波动严重晨跑', '2026-06-10T07:00:00+00:00', '世纪公园', '湖边 5km', 5.0, 'easy', '参与率大幅下降，触发 critical。');

INSERT OR IGNORE INTO member_groups (id, group_key, name, description) VALUES
    (9101, 'new_runner', '新人组', '跑龄 0-1 年或正在建立固定训练习惯的成员。'),
    (9102, 'advanced_runner', '进阶组', '具备稳定训练习惯、通常距离 10km 以上的成员。');

INSERT OR IGNORE INTO member_group_memberships (group_id, member_id, valid_from) VALUES
    (9101, 9102, '2026-05-01'),
    (9101, 9103, '2026-05-01'),
    (9102, 9104, '2026-05-01'),
    (9102, 9105, '2026-05-01');

INSERT OR IGNORE INTO activity_participation_anomaly_thresholds (
    id, scope_type, activity_id, group_id, baseline_window_days, min_sample_activities,
    warning_drop_pp, critical_drop_pp, warning_z_score, critical_z_score, min_participation_rate
) VALUES
    (9101, 'global', NULL, NULL, 30, 3, 15.0, 30.0, -1.5, -2.5, 0.60),
    (9102, 'member_group', NULL, 9101, 30, 3, 20.0, 35.0, -1.5, -2.5, 0.50);

INSERT OR IGNORE INTO registrations (activity_id, member_id, status, created_at) VALUES
    (9101, 9102, 'registered', '2026-05-19T10:00:00+00:00'),
    (9101, 9103, 'registered', '2026-05-19T10:01:00+00:00'),
    (9101, 9104, 'registered', '2026-05-19T10:02:00+00:00'),
    (9101, 9105, 'registered', '2026-05-19T10:03:00+00:00'),
    (9102, 9102, 'registered', '2026-05-26T10:00:00+00:00'),
    (9102, 9103, 'registered', '2026-05-26T10:01:00+00:00'),
    (9102, 9104, 'registered', '2026-05-26T10:02:00+00:00'),
    (9102, 9105, 'registered', '2026-05-26T10:03:00+00:00'),
    (9103, 9102, 'registered', '2026-06-02T10:00:00+00:00'),
    (9103, 9103, 'registered', '2026-06-02T10:01:00+00:00'),
    (9103, 9104, 'registered', '2026-06-02T10:02:00+00:00'),
    (9103, 9105, 'registered', '2026-06-02T10:03:00+00:00'),
    (9104, 9102, 'registered', '2026-06-09T10:00:00+00:00'),
    (9104, 9103, 'registered', '2026-06-09T10:01:00+00:00'),
    (9104, 9104, 'registered', '2026-06-09T10:02:00+00:00'),
    (9104, 9105, 'registered', '2026-06-09T10:03:00+00:00');

INSERT OR IGNORE INTO attendances (activity_id, member_id, status, signed_in_at, gps_checked) VALUES
    (9101, 9102, 'signed_in', '2026-05-20T07:02:00+00:00', 1),
    (9101, 9103, 'signed_in', '2026-05-20T07:03:00+00:00', 1),
    (9101, 9104, 'signed_in', '2026-05-20T07:02:00+00:00', 1),
    (9101, 9105, 'signed_in', '2026-05-20T07:04:00+00:00', 1),
    (9102, 9102, 'signed_in', '2026-05-27T07:02:00+00:00', 1),
    (9102, 9104, 'signed_in', '2026-05-27T07:03:00+00:00', 1),
    (9102, 9105, 'signed_in', '2026-05-27T07:04:00+00:00', 1),
    (9102, 9103, 'absent', '2026-05-27T07:30:00+00:00', 0),
    (9103, 9102, 'signed_in', '2026-06-03T07:02:00+00:00', 1),
    (9103, 9104, 'signed_in', '2026-06-03T07:03:00+00:00', 1),
    (9103, 9103, 'absent', '2026-06-03T07:30:00+00:00', 0),
    (9103, 9105, 'absent', '2026-06-03T07:30:00+00:00', 0),
    (9104, 9102, 'signed_in', '2026-06-10T07:02:00+00:00', 1),
    (9104, 9103, 'absent', '2026-06-10T07:30:00+00:00', 0),
    (9104, 9104, 'absent', '2026-06-10T07:30:00+00:00', 0),
    (9104, 9105, 'absent', '2026-06-10T07:30:00+00:00', 0);

INSERT OR IGNORE INTO activity_participation_daily_metrics (
    activity_id, metric_date, group_id, registered_count, signed_in_count, absent_count,
    cancelled_count, participation_rate, baseline_participation_rate, rate_delta_pp,
    z_score, anomaly_level, threshold_id, calculated_at
) VALUES
    (9101, '2026-05-20', NULL, 4, 4, 0, 0, 1.00, NULL, NULL, NULL, 'insufficient_data', 9101, '2026-06-06T00:00:00+00:00'),
    (9102, '2026-05-27', NULL, 4, 3, 1, 0, 0.75, 1.00, -25.0, -1.0, 'normal', 9101, '2026-06-06T00:00:00+00:00'),
    (9103, '2026-06-03', NULL, 4, 2, 2, 0, 0.50, 0.875, -37.5, -1.8, 'warning', 9101, '2026-06-06T00:00:00+00:00'),
    (9104, '2026-06-10', NULL, 4, 1, 3, 0, 0.25, 0.75, -50.0, -2.7, 'critical', 9101, '2026-06-06T00:00:00+00:00'),
    (9103, '2026-06-03', 9101, 2, 1, 1, 0, 0.50, 0.75, -25.0, -1.6, 'warning', 9102, '2026-06-06T00:00:00+00:00'),
    (9104, '2026-06-10', 9101, 2, 1, 1, 0, 0.50, 0.625, -12.5, -0.8, 'normal', 9102, '2026-06-06T00:00:00+00:00');

COMMIT;
