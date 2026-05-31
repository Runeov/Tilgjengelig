"""SQLite schema + connection helpers for KrobJob.

One file-based DB (default: krobjob/krobjob.db, override with $KROBJOB_DB).
Stdlib-only. Status flows: company.status prospect -> client -> lost.
"""

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "krobjob.db")


def db_path() -> str:
    return os.environ.get("KROBJOB_DB", DEFAULT_DB)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    name_thai     TEXT,
    province      TEXT,
    city          TEXT,
    venue_type    TEXT,           -- bar / show / restaurant / lodging / ...
    subcategory   TEXT,
    phone         TEXT,
    email         TEXT,
    website       TEXT,
    facebook      TEXT,
    instagram     TEXT,
    line_id       TEXT,
    address       TEXT,
    lat           REAL,
    lng           REAL,
    source        TEXT,           -- where the record came from
    status        TEXT NOT NULL DEFAULT 'prospect',  -- prospect|client|lost
    notes         TEXT,
    created_at    TEXT,
    updated_at    TEXT
);

-- Client-specific facts, created when a company is promoted (registers on the app).
CREATE TABLE IF NOT EXISTS clients (
    id              INTEGER PRIMARY KEY,
    company_id      INTEGER NOT NULL UNIQUE REFERENCES companies(id) ON DELETE CASCADE,
    krobjob_account TEXT,
    plan            TEXT,
    account_manager TEXT,
    monthly_fee     REAL,
    status          TEXT NOT NULL DEFAULT 'active',  -- active|paused|churned
    registered_at   TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS social_profiles (
    id           INTEGER PRIMARY KEY,
    company_id   INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    platform     TEXT NOT NULL,   -- facebook|instagram|tiktok|line|x|youtube
    handle       TEXT,
    url          TEXT,
    followers    INTEGER,
    last_checked TEXT,
    UNIQUE(company_id, platform)
);

CREATE TABLE IF NOT EXISTS communications (
    id          INTEGER PRIMARY KEY,
    company_id  INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    channel     TEXT NOT NULL,    -- email|phone|line|facebook|meeting|note
    direction   TEXT NOT NULL DEFAULT 'out',  -- in|out
    subject     TEXT,
    body        TEXT,
    occurred_at TEXT,
    operator    TEXT,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS contracts (
    id          INTEGER PRIMARY KEY,
    company_id  INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'draft',  -- draft|sent|signed|active|expired|cancelled
    value       REAL,
    currency    TEXT DEFAULT 'THB',
    start_date  TEXT,
    end_date    TEXT,
    signed_at   TEXT,
    file_ref    TEXT,
    notes       TEXT,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS sales (
    id          INTEGER PRIMARY KEY,
    company_id  INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    occurred_on TEXT NOT NULL,    -- YYYY-MM-DD
    amount      REAL NOT NULL,
    currency    TEXT DEFAULT 'THB',
    category    TEXT,
    description TEXT,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY,
    company_id  INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    occurred_on TEXT NOT NULL,
    amount      REAL NOT NULL,
    currency    TEXT DEFAULT 'THB',
    category    TEXT,
    description TEXT,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS reports (
    id            INTEGER PRIMARY KEY,
    company_id    INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    kind          TEXT NOT NULL,   -- performance|market_trend
    period_start  TEXT,
    period_end    TEXT,
    summary       TEXT,
    payload_json  TEXT,
    html_path     TEXT,
    generated_at  TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_uniq
    ON companies(name, COALESCE(city,''), COALESCE(address,''));
CREATE INDEX IF NOT EXISTS idx_companies_status   ON companies(status);
CREATE INDEX IF NOT EXISTS idx_companies_province ON companies(province);
CREATE INDEX IF NOT EXISTS idx_companies_vtype    ON companies(venue_type);
CREATE INDEX IF NOT EXISTS idx_sales_company      ON sales(company_id, occurred_on);
CREATE INDEX IF NOT EXISTS idx_expenses_company   ON expenses(company_id, occurred_on);
CREATE INDEX IF NOT EXISTS idx_comms_company      ON communications(company_id, occurred_at);
"""


def init_db() -> str:
    conn = connect()
    with conn:
        conn.executescript(SCHEMA)
    conn.close()
    return db_path()


def find_company(conn: sqlite3.Connection, ident: str):
    """Resolve a company by numeric id or (case-insensitive) name substring."""
    if str(ident).isdigit():
        row = conn.execute("SELECT * FROM companies WHERE id=?", (int(ident),)).fetchone()
        if row:
            return row
    rows = conn.execute(
        "SELECT * FROM companies WHERE name LIKE ? ORDER BY length(name) LIMIT 5",
        (f"%{ident}%",),
    ).fetchall()
    if len(rows) == 1:
        return rows[0]
    if not rows:
        return None
    # Prefer an exact (case-insensitive) match if present.
    for r in rows:
        if r["name"].lower() == str(ident).lower():
            return r
    raise LookupError(
        f"'{ident}' is ambiguous: " + ", ".join(f"[{r['id']}] {r['name']}" for r in rows)
    )
