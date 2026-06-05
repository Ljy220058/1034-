-- Migration 001: create normalized schema for user/content/event platform
PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    external_ref TEXT UNIQUE,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'deleted')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS content_types (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contents (
    id INTEGER PRIMARY KEY,
    content_type_id INTEGER NOT NULL REFERENCES content_types(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    author_user_id INTEGER NOT NULL REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'public' CHECK (visibility IN ('public', 'private', 'unlisted')),
    published_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS content_tags (
    content_id INTEGER NOT NULL REFERENCES contents(id) ON UPDATE CASCADE ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (content_id, tag_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY,
    content_id INTEGER NOT NULL REFERENCES contents(id) ON UPDATE CASCADE ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    parent_comment_id INTEGER REFERENCES comments(id) ON UPDATE CASCADE ON DELETE CASCADE,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (parent_comment_id IS NULL OR parent_comment_id <> id)
);

CREATE TABLE IF NOT EXISTS reactions (
    user_id INTEGER NOT NULL REFERENCES users(id) ON UPDATE CASCADE ON DELETE CASCADE,
    content_id INTEGER REFERENCES contents(id) ON UPDATE CASCADE ON DELETE CASCADE,
    comment_id INTEGER REFERENCES comments(id) ON UPDATE CASCADE ON DELETE CASCADE,
    reaction_type TEXT NOT NULL CHECK (reaction_type IN ('like', 'bookmark', 'laugh', 'sad', 'angry')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK ((content_id IS NOT NULL) <> (comment_id IS NOT NULL)),
    PRIMARY KEY (user_id, content_id, comment_id, reaction_type)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    is_pinned INTEGER NOT NULL DEFAULT 0 CHECK (is_pinned IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    published_at TEXT,
    CHECK (published_at IS NULL OR status = 'published')
);

CREATE INDEX IF NOT EXISTS idx_announcements_status_published ON announcements(status, published_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_announcements_pinned_published ON announcements(is_pinned DESC, published_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_contents_author_published ON contents(author_user_id, published_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_contents_type_published ON contents(content_type_id, published_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_contents_visibility_published ON contents(visibility, published_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_comments_content_created ON comments(content_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_comments_parent_created ON comments(parent_comment_id, created_at ASC, id ASC);
CREATE INDEX IF NOT EXISTS idx_reactions_content ON reactions(content_id, reaction_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reactions_comment ON reactions(comment_id, reaction_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_tags_tag ON content_tags(tag_id, content_id);
CREATE INDEX IF NOT EXISTS idx_contents_published_lookup ON contents(published_at DESC, id DESC) WHERE published_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_status_created ON users(status, created_at DESC, id DESC);

INSERT INTO content_types (code, label) VALUES
    ('article', 'Article'),
    ('note', 'Note'),
    ('announcement', 'Announcement');

INSERT INTO schema_migrations (version, name) VALUES (1, '001_create_core_schema');

COMMIT;
