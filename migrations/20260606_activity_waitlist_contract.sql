-- 迁移：新增活动报名候补队列数据结构
-- 日期：2026-06-06
-- 回滚：执行 migrations/20260606_rollback_activity_waitlist_contract.sql

PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS activity_waitlist_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    waitlist_position INTEGER NOT NULL CHECK (waitlist_position > 0),
    registered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cancelled_at TEXT,
    promotion_status TEXT NOT NULL DEFAULT 'waiting' CHECK (promotion_status IN ('waiting', 'offered', 'promoted', 'expired', 'skipped', 'cancelled', 'conflict_blocked')),
    notification_status TEXT NOT NULL DEFAULT 'pending' CHECK (notification_status IN ('pending', 'sent', 'failed', 'not_required', 'expired')),
    offer_expires_at TEXT,
    promotion_reason TEXT NOT NULL DEFAULT 'member_cancelled' CHECK (promotion_reason IN ('member_cancelled', 'admin_capacity_expanded', 'waitlist_timeout', 'activity_conflict', 'manual_skip')),
    promoted_registration_id INTEGER,
    promoted_at TEXT,
    skipped_at TEXT,
    admin_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
    FOREIGN KEY (promoted_registration_id) REFERENCES registrations(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_activity_waitlist_entries_activity_member_active
    ON activity_waitlist_entries(activity_id, member_id)
    WHERE promotion_status IN ('waiting', 'offered');

CREATE UNIQUE INDEX IF NOT EXISTS uq_activity_waitlist_entries_activity_position_active
    ON activity_waitlist_entries(activity_id, waitlist_position)
    WHERE promotion_status IN ('waiting', 'offered');

CREATE INDEX IF NOT EXISTS idx_activity_waitlist_entries_activity_status_position
    ON activity_waitlist_entries(activity_id, promotion_status, waitlist_position, id);

CREATE INDEX IF NOT EXISTS idx_activity_waitlist_entries_member_status
    ON activity_waitlist_entries(member_id, promotion_status, registered_at DESC);

CREATE INDEX IF NOT EXISTS idx_activity_waitlist_entries_offer_expires_at
    ON activity_waitlist_entries(offer_expires_at, notification_status)
    WHERE promotion_status = 'offered';

CREATE INDEX IF NOT EXISTS idx_activity_waitlist_entries_promoted_registration
    ON activity_waitlist_entries(promoted_registration_id)
    WHERE promoted_registration_id IS NOT NULL;

INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES (2026060601, '20260606_activity_waitlist_contract');

COMMIT;
