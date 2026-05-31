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
HOSPITALITY = os.path.join(DATA, "hospitality_udonthani.csv")
CONTACTS = os.path.join(DATA, "udon_barshow_contacts.csv")


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
    if not os.path.exists(HOSPITALITY):
        raise FileNotFoundError(HOSPITALITY)

    conn = db.connect()
    inserted = skipped = 0
    with conn:
        with open(HOSPITALITY, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                name = (r.get("name") or "").strip()
                if not name:
                    skipped += 1
                    continue
                sub = r.get("subcategory") or r.get("osm_subcategory") or ""
                vt = (r.get("venue_type") or "").strip() or classify(
                    sub, r.get("wongnai_categories"), r.get("category_raw"))
                city = (r.get("city") or "Udon Thani").strip() or "Udon Thani"
                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO companies
                           (name,name_thai,province,city,venue_type,subcategory,
                            phone,email,website,address,lat,lng,source,status,
                            created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, 'prospect', ?, ?)""",
                        (name, r.get("name_thai") or None, "Udon Thani", city, vt or None,
                         r.get("subcategory") or r.get("osm_subcategory") or None,
                         r.get("phone") or None, r.get("email") or None,
                         r.get("website") or None, r.get("address") or None,
                         _f(r.get("lat")), _f(r.get("lng")),
                         r.get("sources") or "hospitality_udonthani", db.now(), db.now()),
                    )
                    inserted += conn.total_changes and 1 or 0
                except Exception:
                    skipped += 1
        # recount precisely
        total = conn.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"]

    enriched = _overlay_contacts(conn)
    conn.close()
    stats = {"companies_total": total, "rows_read": inserted + skipped,
             "enriched_from_contacts": enriched}
    if verbose:
        print(f"[seed] companies in directory: {total}")
        print(f"[seed] enriched from bar/show contacts: {enriched}")
    return stats


def _overlay_contacts(conn) -> int:
    if not os.path.exists(CONTACTS):
        return 0
    enriched = 0
    with conn:
        for r in csv.DictReader(open(CONTACTS, encoding="utf-8")):
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
                vt = classify(r.get("note"), name) or "bar"
                cur = conn.execute(
                    """INSERT OR IGNORE INTO companies
                       (name,province,city,venue_type,phone,email,website,facebook,
                        address,source,status,created_at,updated_at)
                       VALUES (?, 'Udon Thani','Udon Thani',?,?,?,?,?,?,
                               'udon_barshow_contacts','prospect',?,?)""",
                    (key, vt, r.get("phone") or None, r.get("email") or None,
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
