"""SQLite helpers for the outreach webapp."""

import os
import sqlite3
from datetime import datetime, timezone

from flask import g

# data/outreach.sqlite — same data dir as the scrapers
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "outreach.sqlite")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_db() -> sqlite3.Connection:
    """Per-request connection (cached on flask.g)."""
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    """Create tables if missing. Idempotent."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema)
        # Seed one default template if none exist
        cur = conn.execute("SELECT COUNT(*) FROM templates")
        if cur.fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO templates (name, channel, body, is_default, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    "Default intro",
                    "whatsapp",
                    "Hi {shop_name}, I came across your shop in {city} and wanted to reach out — "
                    "do you have a moment to chat?",
                    1,
                    now_iso(),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def log_action(source_id: str, action: str, detail: str = "") -> None:
    db = get_db()
    db.execute(
        "INSERT INTO outreach_log (source_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
        (source_id, action, detail, now_iso()),
    )
    db.commit()


def ensure_outreach_row(source_id: str) -> None:
    """Create the outreach row for a shop if it doesn't exist yet."""
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO outreach (source_id, status, updated_at) VALUES (?, 'new', ?)",
        (source_id, now_iso()),
    )
    db.commit()
