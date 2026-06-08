-- 种子数据：活动参与率分析本地演示数据
-- 日期：2026-06-06
-- 覆盖：已报名未签到、已签到、缺席；可按活动、成员、日期聚合

PRAGMA foreign_keys = ON;

BEGIN;

INSERT OR IGNORE INTO members (
    id, name, phone, role, running_years, pace, usual_distance_km, training_goal, password_hash
) VALUES
    (9001, 'Participation Leader', '15550900001', 'leader', 6, '5:10/km', 12.0, 'Lead participation demo runs', 'seeded-demo-leader'),
    (9002, 'Participation Signed In', '15550900002', 'member', 3, '5:50/km', 10.0, 'Improve attendance consistency', 'seeded-demo-signed-in'),
    (9003, 'Participation Unchecked', '15550900003', 'member', 2, '6:15/km', 8.0, 'Register for weekly runs', 'seeded-demo-unchecked'),
    (9004, 'Participation Absent', '15550900004', 'member', 1, '6:40/km', 6.0, 'Build a regular routine', 'seeded-demo-absent');

INSERT OR IGNORE INTO activities (
    id, title, start_time, location, route, distance_km, pace_group, description
) VALUES
    (9001, 'Participation Demo Morning Run', '2026-06-08T07:00:00+00:00', 'Demo Park', 'Lake loop', 8.0, 'easy', 'Demo activity with signed-in, unchecked, and absent participants.'),
    (9002, 'Participation Demo Tempo Run', '2026-06-10T19:00:00+00:00', 'Demo Track', '6 x 800m', 9.0, 'tempo', 'Second demo activity for member/date aggregation.');

INSERT OR IGNORE INTO registrations (activity_id, member_id, status, created_at) VALUES
    (9001, 9002, 'registered', '2026-06-07T10:00:00+00:00'),
    (9001, 9003, 'registered', '2026-06-07T10:05:00+00:00'),
    (9001, 9004, 'registered', '2026-06-07T10:10:00+00:00'),
    (9002, 9002, 'registered', '2026-06-09T10:00:00+00:00'),
    (9002, 9003, 'registered', '2026-06-09T10:05:00+00:00');

INSERT OR IGNORE INTO attendances (
    activity_id, member_id, status, signed_in_at, gps_checked
) VALUES
    (9001, 9002, 'signed_in', '2026-06-08T07:03:00+00:00', 1),
    (9001, 9004, 'absent', '2026-06-08T07:30:00+00:00', 0),
    (9002, 9002, 'signed_in', '2026-06-10T19:04:00+00:00', 1);

COMMIT;
