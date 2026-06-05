-- Migration 002: add full-text search and audit log tables
PRAGMA foreign_keys = ON;

BEGIN;

CREATE VIRTUAL TABLE IF NOT EXISTS contents_fts USING fts5(
    title,
    body,
    content='contents',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS contents_ai AFTER INSERT ON contents BEGIN
    INSERT INTO contents_fts(rowid, title, body)
    VALUES (new.id, new.title, new.body);
END;

CREATE TRIGGER IF NOT EXISTS contents_ad AFTER DELETE ON contents BEGIN
    INSERT INTO contents_fts(contents_fts, rowid, title, body)
    VALUES ('delete', old.id, old.title, old.body);
END;

CREATE TRIGGER IF NOT EXISTS contents_au AFTER UPDATE OF title, body ON contents BEGIN
    INSERT INTO contents_fts(contents_fts, rowid, title, body)
    VALUES ('delete', old.id, old.title, old.body);
    INSERT INTO contents_fts(rowid, title, body)
    VALUES (new.id, new.title, new.body);
END;

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    actor_user_id INTEGER REFERENCES users(id) ON UPDATE CASCADE ON DELETE SET NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    old_json TEXT,
    new_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (action IN ('insert', 'update', 'delete'))
);

CREATE INDEX IF NOT EXISTS idx_audit_entity_created ON audit_log(entity_type, entity_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor_created ON audit_log(actor_user_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action_created ON audit_log(action, created_at DESC, id DESC);

INSERT INTO schema_migrations (version, name) VALUES (2, '002_add_fts_and_audit');

COMMIT;
