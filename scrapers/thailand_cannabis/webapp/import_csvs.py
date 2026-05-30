"""Import shop data from the scraper CSVs into the outreach SQLite DB.

Source files (in priority order, per shop):
  1. data/leads_<canonical_city>.csv   (preferred; has score + scraped_email)
  2. data/weed_th_<city>_google.csv    (if no leads file yet)
  3. data/weed_th_google.csv           (country-wide enriched; fallback for everything)

Outreach state (status, manual phone/email, notes) is PRESERVED — only shop
columns are overwritten.

Usage:
  python -m scrapers.thailand_cannabis.webapp.import_csvs
  python -m scrapers.thailand_cannabis.webapp.import_csvs --verbose
"""

import argparse
import csv
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from scrapers.thailand_cannabis.city_normalize import canonical_city  # noqa: E402
from scrapers.thailand_cannabis.webapp.db import DATA_DIR, DB_PATH, init_db, now_iso  # noqa: E402

COUNTRY_GOOGLE = os.path.join(DATA_DIR, "weed_th_google.csv")
LEADS_COUNTRY = os.path.join(DATA_DIR, "leads_country.csv")


def _to_int(v):
    try:
        return int(float(v)) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def _to_float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def read_csv(path: str) -> dict[str, dict]:
    """Read CSV into dict keyed by source_id."""
    if not os.path.exists(path):
        return {}
    out: dict[str, dict] = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            sid = r.get("source_id")
            if sid:
                out[sid] = r
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    init_db()

    # Load all sources. leads_*.csv takes precedence per shop; fall back to
    # weed_th_google.csv (country enriched) for shops not in any leads file.
    shops_by_sid: dict[str, dict] = {}

    # 1. Country-wide enriched (base layer)
    base = read_csv(COUNTRY_GOOGLE)
    print(f"[import] base layer: {len(base):,} shops from weed_th_google.csv")
    shops_by_sid.update(base)

    # 2. Country leads file (overlays score + email)
    if os.path.exists(LEADS_COUNTRY):
        leads = read_csv(LEADS_COUNTRY)
        print(f"[import] leads overlay: {len(leads):,} shops from leads_country.csv")
        for sid, row in leads.items():
            if sid in shops_by_sid:
                shops_by_sid[sid].update({k: v for k, v in row.items() if v})
            else:
                shops_by_sid[sid] = row

    # 3. Per-city leads_*.csv files (latest scores for each city)
    per_city_files = sorted(
        f for f in os.listdir(DATA_DIR)
        if f.startswith("leads_") and f.endswith(".csv") and f != "leads_country.csv"
    )
    for fn in per_city_files:
        rows = read_csv(os.path.join(DATA_DIR, fn))
        for sid, row in rows.items():
            if sid in shops_by_sid:
                shops_by_sid[sid].update({k: v for k, v in row.items() if v})
            else:
                shops_by_sid[sid] = row
        if args.verbose:
            print(f"[import] overlaid {len(rows):>4} shops from {fn}")
    print(f"[import] {len(per_city_files)} per-city leads files overlaid")

    # 4. Per-city detail files (older format, smaller subset)
    per_city_google = [
        f for f in os.listdir(DATA_DIR)
        if f.startswith("weed_th_") and f.endswith("_google.csv") and f != "weed_th_google.csv"
    ]
    for fn in per_city_google:
        rows = read_csv(os.path.join(DATA_DIR, fn))
        for sid, row in rows.items():
            if sid in shops_by_sid:
                # Only fill missing fields — don't clobber country-level data
                for k, v in row.items():
                    if v and not shops_by_sid[sid].get(k):
                        shops_by_sid[sid][k] = v
            else:
                shops_by_sid[sid] = row

    print(f"[import] total unique shops to upsert: {len(shops_by_sid):,}")

    # Upsert into DB (preserves outreach state in separate table)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    now = now_iso()
    inserted = 0
    updated = 0
    try:
        for sid, r in shops_by_sid.items():
            raw_city = (r.get("city") or "").strip() or None
            canon = canonical_city(raw_city) if raw_city else None
            payload = {
                "source_id": sid,
                "name": r.get("name") or "",
                "raw_city": raw_city,
                "canonical_city": canon,
                "address": r.get("address") or None,
                "google_phone": r.get("google_phone") or None,
                "google_website": r.get("google_website") or None,
                "google_hours": r.get("google_hours") or None,
                "google_maps_uri": r.get("google_maps_uri") or None,
                "google_user_ratings": _to_int(r.get("google_user_ratings")),
                "google_rating": _to_float(r.get("google_rating") or r.get("rating")),
                "google_match_confidence": r.get("google_match_confidence") or None,
                "scraped_email": r.get("scraped_email") or None,
                "lead_score": _to_int(r.get("lead_score")),
                "lead_quality": _to_int(r.get("lead_quality")),
                "detail_url": r.get("detail_url") or None,
                "last_imported_at": now,
            }
            existed = conn.execute(
                "SELECT 1 FROM shops WHERE source_id = ?", (sid,)
            ).fetchone()
            cols = list(payload.keys())
            placeholders = ", ".join(["?"] * len(cols))
            assignments = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "source_id")
            conn.execute(
                f"INSERT INTO shops ({', '.join(cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT(source_id) DO UPDATE SET {assignments}",
                tuple(payload.values()),
            )
            if existed:
                updated += 1
            else:
                inserted += 1
        conn.commit()
    finally:
        conn.close()

    print(f"[import] done: {inserted:,} new shops, {updated:,} updated")
    print(f"[import] DB: {DB_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
