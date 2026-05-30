-- Local outreach DB. One SQLite file at data/outreach.sqlite.
-- shops: snapshot of the scraped data, keyed by weed.th source_id (uuid).
-- Re-importing CSVs overwrites the shop columns but PRESERVES outreach state
-- (status, notes, manual phone/email overrides, outreach_log).
CREATE TABLE IF NOT EXISTS shops (
    source_id          TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    raw_city           TEXT,
    canonical_city     TEXT,
    address            TEXT,
    google_phone       TEXT,
    google_website     TEXT,
    google_hours       TEXT,
    google_maps_uri    TEXT,
    google_user_ratings INTEGER,
    google_rating      REAL,
    google_match_confidence TEXT,
    scraped_email      TEXT,
    lead_score         INTEGER,
    lead_quality       INTEGER,
    detail_url         TEXT,
    last_imported_at   TEXT
);

CREATE INDEX IF NOT EXISTS idx_shops_city ON shops(canonical_city);
CREATE INDEX IF NOT EXISTS idx_shops_score ON shops(lead_score DESC);

-- Outreach state per shop. Survives CSV re-imports.
-- status: new | messaged | replied | interested | no_answer | closed
CREATE TABLE IF NOT EXISTS outreach (
    source_id    TEXT PRIMARY KEY REFERENCES shops(source_id) ON DELETE CASCADE,
    status       TEXT NOT NULL DEFAULT 'new',
    manual_phone TEXT,
    manual_email TEXT,
    notes        TEXT,
    updated_at   TEXT NOT NULL
);

-- Append-only log of every action you take. Useful for "what did I do yesterday"
-- and as evidence trail if a shop replies.
-- action: viewed | whatsapp_opened | called | emailed | status_changed | note_added | edited
CREATE TABLE IF NOT EXISTS outreach_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    TEXT NOT NULL,
    action       TEXT NOT NULL,
    detail       TEXT,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_log_shop ON outreach_log(source_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_log_time ON outreach_log(created_at DESC);

-- WhatsApp/email message templates with {shop_name} / {city} merge fields.
CREATE TABLE IF NOT EXISTS templates (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    channel    TEXT NOT NULL DEFAULT 'whatsapp', -- whatsapp | email
    body       TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
