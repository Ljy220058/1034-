-- 样例：3 个跑步活动数据质量评分结果
-- 日期：2026-06-06
-- 用途：验收演示，覆盖高驰、佳明、CSV/JSON 导入后的评分输入形态。
-- 注意：这是样例数据脚本，不作为生产迁移自动执行。

PRAGMA foreign_keys = ON;

BEGIN;

INSERT INTO activities (id, title, start_time, location, route, distance_km, pace_group, description, max_participants)
VALUES
    (9001, '高驰晨跑样例', '2026-06-01 06:30:00', '奥森南园', '南园 5 公里环线', 5.02, '5:30/km', '高驰手表同步，GPS 点完整', 30),
    (9002, '佳明长距离样例', '2026-06-02 07:00:00', '滨江绿道', '滨江 10 公里折返', 10.14, '5:45/km', '佳明同步，存在轻微重复风险', 40),
    (9003, 'CSV/JSON 导入补录样例', '2026-06-03 19:30:00', '操场', '400 米跑道', 3.00, '6:40/km', 'CSV/JSON 导入，GPS 点较少', 20)
ON CONFLICT(id) DO NOTHING;

INSERT INTO activity_data_quality_scores (
    activity_id,
    source_platform,
    source_record_id,
    scoring_version,
    distance_km,
    duration_seconds,
    pace_seconds_per_km,
    gps_point_count,
    duplicate_risk_score,
    quality_score,
    quality_level,
    explanation_zh,
    raw_payload_json
)
VALUES
    (
        9001,
        'coros',
        'coros-demo-9001',
        'activity-quality-v1',
        5.02,
        1656,
        330,
        1240,
        5,
        96,
        'excellent',
        '数据质量优秀：距离、配速和时长互相匹配，GPS 点数量充足，来源为高驰同步，重复风险很低。',
        '{"distance_km":5.02,"duration_seconds":1656,"pace_seconds_per_km":330,"gps_point_count":1240,"source_platform":"coros"}'
    ),
    (
        9002,
        'garmin',
        'garmin-demo-9002',
        'activity-quality-v1',
        10.14,
        3498,
        345,
        2100,
        25,
        84,
        'good',
        '数据质量良好：佳明同步数据完整，距离与配速基本一致；检测到轻微重复风险，建议前端提示用户确认是否为同一次活动。',
        '{"distance_km":10.14,"duration_seconds":3498,"pace_seconds_per_km":345,"gps_point_count":2100,"source_platform":"garmin","duplicate_risk_score":25}'
    ),
    (
        9003,
        'csv',
        'csv-json-demo-9003',
        'activity-quality-v1',
        3.00,
        1200,
        400,
        18,
        60,
        58,
        'fair',
        '数据质量一般：CSV/JSON 导入提供了距离、配速和时长，但 GPS 点数量偏少且重复风险较高，建议人工复核后再用于排行榜。',
        '{"distance_km":3.00,"duration_seconds":1200,"pace_seconds_per_km":400,"gps_point_count":18,"source_platform":"csv","import_format":"json-compatible"}'
    )
ON CONFLICT(activity_id, scoring_version) DO UPDATE SET
    source_platform = excluded.source_platform,
    source_record_id = excluded.source_record_id,
    distance_km = excluded.distance_km,
    duration_seconds = excluded.duration_seconds,
    pace_seconds_per_km = excluded.pace_seconds_per_km,
    gps_point_count = excluded.gps_point_count,
    duplicate_risk_score = excluded.duplicate_risk_score,
    quality_score = excluded.quality_score,
    quality_level = excluded.quality_level,
    explanation_zh = excluded.explanation_zh,
    raw_payload_json = excluded.raw_payload_json,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO activity_data_quality_score_reasons (
    quality_score_id,
    reason_code,
    reason_type,
    impact_points,
    message_zh,
    display_order
)
SELECT id, 'gps_points_sufficient', 'bonus', 8, 'GPS 点数量充足，轨迹可信度高。', 10
FROM activity_data_quality_scores WHERE activity_id = 9001
ON CONFLICT(quality_score_id, reason_code) DO UPDATE SET
    reason_type = excluded.reason_type,
    impact_points = excluded.impact_points,
    message_zh = excluded.message_zh,
    display_order = excluded.display_order,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO activity_data_quality_score_reasons (quality_score_id, reason_code, reason_type, impact_points, message_zh, display_order)
SELECT id, 'low_duplicate_risk', 'bonus', 6, '重复风险很低，可直接展示。', 20
FROM activity_data_quality_scores WHERE activity_id = 9001
ON CONFLICT(quality_score_id, reason_code) DO UPDATE SET
    reason_type = excluded.reason_type,
    impact_points = excluded.impact_points,
    message_zh = excluded.message_zh,
    display_order = excluded.display_order,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO activity_data_quality_score_reasons (quality_score_id, reason_code, reason_type, impact_points, message_zh, display_order)
SELECT id, 'minor_duplicate_risk', 'penalty', -8, '存在轻微重复风险，建议提示用户确认。', 10
FROM activity_data_quality_scores WHERE activity_id = 9002
ON CONFLICT(quality_score_id, reason_code) DO UPDATE SET
    reason_type = excluded.reason_type,
    impact_points = excluded.impact_points,
    message_zh = excluded.message_zh,
    display_order = excluded.display_order,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO activity_data_quality_score_reasons (quality_score_id, reason_code, reason_type, impact_points, message_zh, display_order)
SELECT id, 'few_gps_points', 'penalty', -18, 'GPS 点数量偏少，轨迹完整性不足。', 10
FROM activity_data_quality_scores WHERE activity_id = 9003
ON CONFLICT(quality_score_id, reason_code) DO UPDATE SET
    reason_type = excluded.reason_type,
    impact_points = excluded.impact_points,
    message_zh = excluded.message_zh,
    display_order = excluded.display_order,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO activity_data_quality_score_reasons (quality_score_id, reason_code, reason_type, impact_points, message_zh, display_order)
SELECT id, 'high_duplicate_risk', 'penalty', -22, '重复风险较高，不建议直接进入排行榜。', 20
FROM activity_data_quality_scores WHERE activity_id = 9003
ON CONFLICT(quality_score_id, reason_code) DO UPDATE SET
    reason_type = excluded.reason_type,
    impact_points = excluded.impact_points,
    message_zh = excluded.message_zh,
    display_order = excluded.display_order,
    updated_at = CURRENT_TIMESTAMP;

COMMIT;
