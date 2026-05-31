"""Seed the company directory from the Udon Thani hospitality data.

Imports every company from scrapers/thailand_hospitality/data/hospitality_udonthani.csv
as a prospect, then overlays the manually-enriched bar/show contacts
(udon_barshow_contacts.csv) to fill phone/email/website/facebook/address by name.
"""

import csv
import os

from . import db

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "scrapers", "thailand_hospitality", "data")

# Per-city contact overlays: the reusable engine writes contacts_<slug>.csv;
# Udon also has the original udon_barshow_contacts.csv. Both share the columns
# _overlay_contacts reads (name/phone/email/website/facebook/address).
LEGACY_CONTACTS = {"udonthani": "udon_barshow_contacts.csv"}


def hospitality_path(slug: str) -> str:
    return os.path.join(DATA, f"hospitality_{slug}.csv")


def contacts_paths(slug: str) -> list:
    # Prefer the engine's standard file; fall back to a legacy file only if the
    # standard one doesn't exist yet (avoids double-counting the same venues).
    std = os.path.join(DATA, f"contacts_{slug}.csv")
    if os.path.exists(std):
        return [std]
    if slug in LEGACY_CONTACTS:
        legacy = os.path.join(DATA, LEGACY_CONTACTS[slug])
        if os.path.exists(legacy):
            return [legacy]
    return []


def _norm(s: str) -> str:
    return (s or "").strip().lower()


# The merged hospitality CSV has no venue_type column, so derive it from the
# OSM/Wongnai subcategory text (same taxonomy as scrape_osm.venue_type_for).
_BAR = ("bar", "pub", "nightclub", "stripclub", "lounge", "beer")
_SHOW = ("theatre", "theater", "cinema", "arts_centre", "stadium", "dance",
         "muay", "boxing", "cabaret", "live music")
_FOOD = ("restaurant", "cafe", "café", "noodle", "food", "bakery", "coffee")
_LODGING = ("hotel", "guest_house", "guesthouse", "hostel", "motel", "resort", "apartment")


def classify(*texts) -> str:
    blob = " ".join(t or "" for t in texts).lower()
    if any(k in blob for k in _BAR):
        return "bar"
    if any(k in blob for k in _SHOW):
        return "show"
    if any(k in blob for k in _LODGING):
        return "lodging"
    if any(k in blob for k in _FOOD):
        return "restaurant"
    return ""


def seed_udon(verbose: bool = True) -> dict:
    return seed_city("udonthani", "Udon Thani", verbose)


def seed_city(slug: str, province: str, verbose: bool = True) -> dict:
    """Generic importer: hospitality_<slug>.csv directory + contacts_<slug>.csv
    overlay. This is the one call that onboards a new city."""
    hp = hospitality_path(slug)
    if not os.path.exists(hp):
        raise FileNotFoundError(hp)

    conn = db.connect()
    inserted = skipped = 0
    with conn:
        with open(hp, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                name = (r.get("name") or "").strip()
                if not name:
                    skipped += 1
                    continue
                sub = r.get("subcategory") or r.get("osm_subcategory") or ""
                vt = (r.get("venue_type") or "").strip() or classify(
                    sub, r.get("wongnai_categories"), r.get("category_raw"))
                city = (r.get("city") or province).strip() or province
                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO companies
                           (name,name_thai,province,city,venue_type,subcategory,
                            phone,email,website,address,lat,lng,source,status,
                            created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, 'prospect', ?, ?)""",
                        (name, r.get("name_thai") or None, province, city, vt or None,
                         r.get("subcategory") or r.get("osm_subcategory") or None,
                         r.get("phone") or None, r.get("email") or None,
                         r.get("website") or None, r.get("address") or None,
                         _f(r.get("lat")), _f(r.get("lng")),
                         r.get("sources") or f"hospitality_{slug}", db.now(), db.now()),
                    )
                    inserted += conn.total_changes and 1 or 0
                except Exception:
                    skipped += 1
        total = conn.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"]

    enriched = 0
    for cp in contacts_paths(slug):
        enriched += _overlay_contacts(conn, cp, province)
    conn.close()
    stats = {"companies_total": total, "rows_read": inserted + skipped,
             "enriched_from_contacts": enriched}
    if verbose:
        print(f"[seed:{slug}] companies in directory: {total}")
        print(f"[seed:{slug}] enriched from contacts: {enriched}")
    return stats


def _overlay_contacts(conn, contacts_file: str, province: str) -> int:
    if not os.path.exists(contacts_file):
        return 0
    enriched = 0
    with conn:
        for r in csv.DictReader(open(contacts_file, encoding="utf-8")):
            name = (r.get("name") or "").strip()
            if not name:
                continue
            # match the leading part of names like "Country Road / Country Bar"
            key = name.split(" / ")[0]
            row = conn.execute(
                "SELECT id FROM companies WHERE lower(name)=? LIMIT 1", (_norm(key),)
            ).fetchone()
            if not row:
                # Enriched venue not yet in the directory → add it as a prospect.
                vt = (r.get("venue_type") or "").strip() or classify(r.get("note"), name) or "bar"
                cur = conn.execute(
                    """INSERT OR IGNORE INTO companies
                       (name,province,city,venue_type,phone,email,website,facebook,
                        address,source,status,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?, 'contacts_overlay','prospect',?,?)""",
                    (key, province, r.get("city") or province, vt,
                     r.get("phone") or None, r.get("email") or None,
                     r.get("website") or None, r.get("facebook") or None,
                     r.get("address") or None, db.now(), db.now()))
                row = conn.execute("SELECT id FROM companies WHERE lower(name)=? LIMIT 1",
                                   (_norm(key),)).fetchone()
                if not row:
                    continue
                if r.get("facebook"):
                    conn.execute(
                        """INSERT OR IGNORE INTO social_profiles(company_id,platform,url,last_checked)
                           VALUES (?, 'facebook', ?, ?)""", (row["id"], r["facebook"], db.now()))
                enriched += 1
                continue
            conn.execute(
                """UPDATE companies SET
                     phone    = COALESCE(NULLIF(phone,''), ?),
                     email    = COALESCE(NULLIF(email,''), ?),
                     website  = COALESCE(NULLIF(website,''), ?),
                     facebook = COALESCE(NULLIF(facebook,''), ?),
                     address  = COALESCE(NULLIF(address,''), ?),
                     source   = source || ' + enriched',
                     updated_at = ?
                   WHERE id=?""",
                (r.get("phone") or None, r.get("email") or None, r.get("website") or None,
                 r.get("facebook") or None, r.get("address") or None, db.now(), row["id"]),
            )
            # mirror facebook into social_profiles
            if r.get("facebook"):
                conn.execute(
                    """INSERT OR IGNORE INTO social_profiles(company_id,platform,url,last_checked)
                       VALUES (?, 'facebook', ?, ?)""",
                    (row["id"], r["facebook"], db.now()),
                )
            enriched += 1
    return enriched


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
