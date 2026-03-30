#!/usr/bin/env python3
"""
Nord-Norge & Svalbard Travel Company Harvester
===============================================
Fetches all travel/tourism companies in northern Norway from two sources:
  1. Brønnøysund Enhetsregisteret (free open API — authoritative registry)
  2. proff.no website URLs (Playwright scrape, enriches the dataset)

Covers: Nordland, Troms, Finnmark, Svalbard
Target: ~1358 companies in Nord-Norge + 91 in Svalbard

NACE codes harvested (Norwegian travel industry):
  55.x  — Accommodation (hotels, camping, cabins, hostels)
  79.x  — Travel agencies & tour operators
  93.2x — Recreation & attraction activities
  49.39 — Other passenger transport (excl. railway)
  50.1x — Sea/coastal passenger transport (Hurtigruten, ferries)

Output:
  nordnorge_travel_companies.csv  — flat CSV, all fields
  nordnorge_travel.db             — SQLite with FTS5 full-text search

Usage:
    python fetch_nordnorge_travel.py                  # Full run
    python fetch_nordnorge_travel.py --nace 79        # Only travel agencies
    python fetch_nordnorge_travel.py --county Finnmark
    python fetch_nordnorge_travel.py --skip-websites  # Skip proff.no lookup
    python fetch_nordnorge_travel.py --svalbard-only
"""

import argparse
import csv
import json
import os
import re
import sqlite3
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse, quote

import requests

# ── Configuration ─────────────────────────────────────────────────────────────

BRREG_API     = "https://data.brreg.no/enhetsregisteret/api/enheter"
BRREG_UNDER   = "https://data.brreg.no/enhetsregisteret/api/underenheter"
PAGE_SIZE     = 100           # Max records per Brønnøysund API page
REQUEST_DELAY = 0.4           # Seconds between API calls (be polite)
PROFF_DELAY   = 1.5           # Seconds between proff.no page fetches

OUTPUT_CSV    = "nordnorge_travel_companies.csv"
OUTPUT_DB     = "nordnorge_travel.db"
CHECKPOINT    = "nordnorge_harvest_checkpoint.json"

# Counties that make up Nord-Norge (all historical name variants)
NORD_NORGE_COUNTIES = {
    "Nordland",
    "Troms",
    "Finnmark",
    "Troms og Finnmark",      # 2020-2024 merged county
    "Svalbard",
}

SVALBARD_ONLY_COUNTIES = {"Svalbard"}

# Travel-related NACE codes (Norwegian standard)
TRAVEL_NACE_CODES = [
    # Accommodation
    "55.100",   # Hotels and similar
    "55.201",   # Youth hostels and holiday centres
    "55.202",   # Camping and caravan sites
    "55.203",   # Cabin rental
    "55.300",   # Short-stay holiday homes / Airbnb-type
    # Travel services
    "79.110",   # Travel agency activities
    "79.120",   # Tour operator activities
    "79.900",   # Other reservation service and related
    # Recreation & attractions
    "93.211",   # Amusement parks
    "93.212",   # Ski resorts and ski lifts
    "93.291",   # Sports and recreation activities
    "93.292",   # Operation of historical sites and attractions
    "93.299",   # Other amusement and recreation activities
    # Transport (relevant for tours)
    "49.391",   # Other passenger land transport (excl. rail)
    "50.101",   # Sea and coastal passenger water transport
    "50.301",   # Inland passenger water transport
    # Food (core travel service)
    "56.101",   # Restaurants
    "56.210",   # Event catering
    # Culture
    "90.011",   # Performing arts
    "91.020",   # Museums
    "91.040",   # Botanical/zoological gardens and nature reserves
]

# CSV output columns
CSV_COLUMNS = [
    "org_nr",
    "name",
    "org_form",
    "nace_code",
    "nace_description",
    "status",                 # active / dissolved / bankrupt
    "employees",
    "street_address",
    "postal_code",
    "postal_place",
    "municipality",
    "municipality_nr",
    "county",
    "founded_year",
    "website",               # from proff.no lookup
    "proff_url",             # direct proff.no company page
    "phone",                 # from proff.no
    "email",                 # from proff.no
    "parent_org_nr",         # for sub-units
    "is_sub_unit",
    "latitude",
    "longitude",
    "fetched_at",
]


# ─────────────────────────────────────────────────────────────────────────────
# Brønnøysund API helpers
# ─────────────────────────────────────────────────────────────────────────────

def _brreg_get(url: str, params: dict) -> dict | None:
    """Single Brønnøysund API call with retry."""
    for attempt in range(3):
        try:
            resp = requests.get(
                url, params=params, timeout=20,
                headers={"Accept": "application/json"}
            )
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                print(f"  Rate limited — waiting 10s...")
                time.sleep(10)
            else:
                print(f"  BRREG HTTP {resp.status_code} for {url}")
                return None
        except Exception as e:
            print(f"  BRREG error (attempt {attempt+1}): {e}")
            time.sleep(2)
    return None


def _parse_entity(entity: dict, is_sub: bool = False) -> dict:
    """Parse a Brønnøysund entity dict into our flat schema."""
    addr = entity.get("forretningsadresse") or entity.get("beliggenhetsadresse") or {}
    nace = (entity.get("naeringskode1") or {})

    # County: Brønnøysund returns it in the address block
    county = addr.get("fylke", "")
    # Some entities have it in kommunenavn block
    if not county:
        county = addr.get("landkode", "")

    # Determine active/dissolved status
    konkurs  = entity.get("konkurs", False)
    avvikl   = entity.get("underAvvikling", False)
    slettet  = entity.get("slettedato")
    if konkurs:
        status = "bankrupt"
    elif slettet:
        status = "dissolved"
    elif avvikl:
        status = "winding_down"
    else:
        status = "active"

    # Extract address lines
    adresse_lines = addr.get("adresse", [])
    street = ", ".join(adresse_lines) if adresse_lines else ""

    # Founded year
    stiftet = entity.get("stiftelsesdato", "") or ""
    founded_year = stiftet[:4] if stiftet else ""

    # Employee count
    ansatte = entity.get("antallAnsatte")

    # Parent (for sub-units)
    parent = entity.get("overordnetEnhet", "")

    return {
        "org_nr":           entity.get("organisasjonsnummer", ""),
        "name":             entity.get("navn", ""),
        "org_form":         (entity.get("organisasjonsform") or {}).get("kode", ""),
        "nace_code":        nace.get("kode", ""),
        "nace_description": nace.get("beskrivelse", ""),
        "status":           status,
        "employees":        str(ansatte) if ansatte is not None else "",
        "street_address":   street,
        "postal_code":      addr.get("postnummer", ""),
        "postal_place":     addr.get("poststed", ""),
        "municipality":     addr.get("kommune", ""),
        "municipality_nr":  addr.get("kommunenummer", ""),
        "county":           county,
        "founded_year":     founded_year,
        "website":          "",
        "proff_url":        "",
        "phone":            "",
        "email":            "",
        "parent_org_nr":    str(parent) if parent else "",
        "is_sub_unit":      "yes" if is_sub else "no",
        "latitude":         "",
        "longitude":        "",
        "fetched_at":       datetime.now().isoformat(),
    }


def _is_nord_norge(entity_dict: dict, svalbard_only: bool = False) -> bool:
    """Check if a parsed entity is in Nord-Norge (or Svalbard only)."""
    county   = entity_dict.get("county", "").strip()
    place    = entity_dict.get("postal_place", "").upper()
    mun_nr   = entity_dict.get("municipality_nr", "")

    # Match by county name
    target = SVALBARD_ONLY_COUNTIES if svalbard_only else NORD_NORGE_COUNTIES
    if county in target:
        return True

    # Fallback: municipality number ranges
    try:
        nr = int(mun_nr)
    except (ValueError, TypeError):
        nr = 0

    if svalbard_only:
        return nr == 2111   # Svalbard

    # Nordland: 1804-1875
    if 1804 <= nr <= 1875:
        return True
    # Old Troms: 1901-1943, old Finnmark: 2002-2030
    if 1901 <= nr <= 1943 or 2002 <= nr <= 2030:
        return True
    # 2020+ merged Troms og Finnmark: 5401-5460
    if 5401 <= nr <= 5460:
        return True
    # 2024+ re-split: Troms 5501-5530, Finnmark 5601-5630 (approx)
    if 5501 <= nr <= 5630:
        return True
    # Svalbard
    if nr == 2111:
        return True

    # Known Svalbard postal codes
    if place in ("LONGYEARBYEN", "BARENTSBURG", "NY-ÅLESUND", "SVEA"):
        return True

    return False


def fetch_nace_page(nace_code: str, page: int, endpoint: str = BRREG_API) -> tuple:
    """
    Fetch one page of results for a NACE code.
    Returns (entities_list, total_pages).
    """
    params = {
        "naeringskode": nace_code,
        "size": PAGE_SIZE,
        "page": page,
        "sort": "navn,asc",
    }
    data = _brreg_get(endpoint, params)
    if not data:
        return [], 0

    entities = data.get("_embedded", {}).get("enheter") or \
               data.get("_embedded", {}).get("underenheter") or []
    page_info = data.get("page", {})
    total_pages = page_info.get("totalPages", 1)
    return entities, total_pages


def fetch_all_for_nace(
    nace_code: str,
    svalbard_only: bool = False,
    county_filter: str = None,
    include_sub_units: bool = True,
) -> list:
    """Fetch all Nord-Norge companies for one NACE code (main + sub-units)."""
    results = []
    short = nace_code.replace(".", "")

    for endpoint, is_sub, label in [
        (BRREG_API,   False, "enheter"),
        (BRREG_UNDER, True,  "underenheter"),
    ] if include_sub_units else [(BRREG_API, False, "enheter")]:

        page = 0
        while True:
            entities, total_pages = fetch_nace_page(nace_code, page, endpoint)

            for ent in entities:
                parsed = _parse_entity(ent, is_sub=is_sub)

                if not _is_nord_norge(parsed, svalbard_only=svalbard_only):
                    continue
                if county_filter and parsed.get("county", "").lower() != county_filter.lower():
                    # Also check partial match (e.g. "Finnmark" matches "Troms og Finnmark")
                    if county_filter.lower() not in parsed.get("county", "").lower():
                        if county_filter.lower() not in parsed.get("municipality", "").lower():
                            continue

                results.append(parsed)

            page += 1
            if page >= total_pages:
                break
            time.sleep(REQUEST_DELAY)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# proff.no enrichment (website URLs, phone, email)
# ─────────────────────────────────────────────────────────────────────────────

def _get_proff_url(org_nr: str) -> str:
    """Build the proff.no URL for a given org.nr."""
    # proff.no company URLs are like:
    # https://www.proff.no/firma/company-name/org-nr/
    # But we can use the direct org.nr lookup:
    return f"https://www.proff.no/selskap/-/-/{org_nr}/"


def enrich_from_proff(companies: list) -> list:
    """
    For each company, fetch its proff.no page to extract:
      - Official website URL
      - Phone number
      - Email address
    Uses plain HTTP requests only (no Playwright).
    Updates company dicts in-place.
    """
    print(f"\nEnriching {len(companies)} companies from proff.no...")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "nb,no,nn,en;q=0.5",
    })

    # Regex patterns for extraction from proff.no HTML
    website_re = re.compile(
        r'href="(https?://(?!www\.proff\.no)[^"]{4,80})"[^>]*>\s*(?:Nettside|Website|www\.|http)',
        re.IGNORECASE
    )
    # proff.no often puts the website in a specific data attribute or link
    website_re2 = re.compile(
        r'"websiteUrl"\s*:\s*"(https?://[^"]{4,80})"',
        re.IGNORECASE
    )
    # Also match simple external links that are likely the company website
    website_re3 = re.compile(
        r'href="(https?://(?!www\.proff\.no|www\.google|www\.facebook)[^"]{8,80})"'
        r'[^>]*(?:rel="noopener|target="_blank")',
        re.IGNORECASE
    )
    phone_re = re.compile(r'\b((?:\+47|0047)?\s*[2-9]\d{7})\b')
    email_re = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

    enriched = 0
    for i, company in enumerate(companies):
        org_nr = company.get("org_nr", "")
        if not org_nr:
            continue

        proff_url = _get_proff_url(org_nr)
        company["proff_url"] = proff_url

        if i % 50 == 0:
            print(f"  [{i+1}/{len(companies)}] {company['name'][:40]}...")

        try:
            resp = session.get(proff_url, timeout=12, allow_redirects=True)
            html = resp.text if resp.status_code == 200 else None

            if not html:
                time.sleep(PROFF_DELAY)
                continue

            # Extract website
            m = website_re.search(html) or website_re2.search(html) or website_re3.search(html)
            if m:
                company["website"] = m.group(1).strip().rstrip("/")
                enriched += 1

            # Extract phone
            phones = phone_re.findall(html[:5000])
            if phones:
                company["phone"] = phones[0].strip()

            # Extract email (avoid proff.no's own emails)
            emails = [e for e in email_re.findall(html)
                      if "proff.no" not in e and "proff@" not in e]
            if emails:
                company["email"] = emails[0]

        except Exception:
            pass  # Continue silently — website lookup is best-effort

        time.sleep(PROFF_DELAY)

    print(f"  Beriking ferdig: {enriched}/{len(companies)} fikk nettsted-URL")
    return companies


# ─────────────────────────────────────────────────────────────────────────────
# CSV & SQLite persistence
# ─────────────────────────────────────────────────────────────────────────────

def save_csv(companies: list, path: str):
    """Write companies to CSV, deduplicating on org_nr."""
    # Deduplicate
    seen = {}
    for c in companies:
        key = c["org_nr"] or c["name"]
        if key not in seen:
            seen[key] = c
        else:
            # Prefer active status
            if c.get("status") == "active":
                seen[key] = c

    rows = list(seen.values())
    rows.sort(key=lambda x: (x.get("county", ""), x.get("municipality", ""), x.get("name", "")))

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nCSV lagret: {path} ({len(rows)} virksomheter)")
    return rows


def build_sqlite(companies: list, db_path: str):
    """
    Build a SQLite database with:
      - companies table (all columns)
      - companies_fts virtual table (FTS5 full-text search)
      - Summary views
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Main table
    cur.executescript("""
        DROP TABLE IF EXISTS companies_fts;
        DROP TABLE IF EXISTS companies;

        CREATE TABLE companies (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            org_nr          TEXT UNIQUE,
            name            TEXT NOT NULL,
            org_form        TEXT,
            nace_code       TEXT,
            nace_description TEXT,
            status          TEXT,
            employees       TEXT,
            street_address  TEXT,
            postal_code     TEXT,
            postal_place    TEXT,
            municipality    TEXT,
            municipality_nr TEXT,
            county          TEXT,
            founded_year    TEXT,
            website         TEXT,
            proff_url       TEXT,
            phone           TEXT,
            email           TEXT,
            parent_org_nr   TEXT,
            is_sub_unit     TEXT,
            latitude        TEXT,
            longitude       TEXT,
            fetched_at      TEXT
        );

        CREATE INDEX idx_county      ON companies(county);
        CREATE INDEX idx_municipality ON companies(municipality);
        CREATE INDEX idx_nace        ON companies(nace_code);
        CREATE INDEX idx_status      ON companies(status);
        CREATE INDEX idx_has_website ON companies(website);
    """)

    # Insert companies
    placeholders = ", ".join(["?" for _ in CSV_COLUMNS])
    sql = f"INSERT OR REPLACE INTO companies ({', '.join(CSV_COLUMNS)}) VALUES ({placeholders})"

    for c in companies:
        cur.execute(sql, [c.get(col, "") for col in CSV_COLUMNS])

    # FTS5 virtual table for full-text search
    cur.executescript("""
        CREATE VIRTUAL TABLE companies_fts USING fts5(
            org_nr,
            name,
            nace_description,
            street_address,
            postal_place,
            municipality,
            county,
            website,
            content=companies,
            content_rowid=id
        );

        INSERT INTO companies_fts(
            rowid, org_nr, name, nace_description, street_address,
            postal_place, municipality, county, website
        )
        SELECT id, org_nr, name, nace_description, street_address,
               postal_place, municipality, county, website
        FROM companies;
    """)

    # Summary views
    cur.executescript("""
        DROP VIEW IF EXISTS summary_by_county;
        CREATE VIEW summary_by_county AS
            SELECT
                county,
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'active'  THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN website != '' THEN 1 ELSE 0 END) AS has_website,
                SUM(CASE WHEN is_sub_unit = 'no' THEN 1 ELSE 0 END) AS main_entities
            FROM companies
            GROUP BY county
            ORDER BY total DESC;

        DROP VIEW IF EXISTS summary_by_nace;
        CREATE VIEW summary_by_nace AS
            SELECT
                nace_code,
                nace_description,
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active
            FROM companies
            GROUP BY nace_code
            ORDER BY total DESC;

        DROP VIEW IF EXISTS summary_by_municipality;
        CREATE VIEW summary_by_municipality AS
            SELECT
                county,
                municipality,
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN website != '' THEN 1 ELSE 0 END) AS has_website
            FROM companies
            GROUP BY municipality
            ORDER BY county, total DESC;
    """)

    conn.commit()
    conn.close()
    print(f"SQLite database lagret: {db_path}")


def print_db_summary(db_path: str):
    """Print a quick summary of the database contents."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("\n" + "=" * 60)
    print("  DATABASE SAMMENDRAG")
    print("=" * 60)

    total = cur.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    active = cur.execute("SELECT COUNT(*) FROM companies WHERE status='active'").fetchone()[0]
    with_web = cur.execute("SELECT COUNT(*) FROM companies WHERE website!=''").fetchone()[0]
    print(f"  Totalt:          {total}")
    print(f"  Aktive:          {active}")
    print(f"  Med nettsted:    {with_web}")

    print("\n  Etter fylke:")
    for row in cur.execute("SELECT * FROM summary_by_county"):
        print(f"    {row['county']:<30} {row['total']:>5} totalt  "
              f"({row['active']} aktive, {row['has_website']} med nettsted)")

    print("\n  Topp 10 NACE-koder:")
    for row in cur.execute("SELECT * FROM summary_by_nace LIMIT 10"):
        print(f"    {row['nace_code']:<10} {row['nace_description']:<45} {row['total']:>4}")

    conn.close()


def load_checkpoint() -> dict:
    """Load previously fetched org.nrs to avoid duplicate API calls."""
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT, encoding="utf-8") as f:
            return json.load(f)
    return {"fetched_nace_codes": [], "companies": []}


def save_checkpoint(state: dict):
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Harvest all travel companies in Nord-Norge + Svalbard"
    )
    parser.add_argument(
        "--nace", help="Filter to specific NACE prefix, e.g. '79' or '55.100'"
    )
    parser.add_argument(
        "--county", help="Filter to county name, e.g. 'Finnmark', 'Nordland', 'Svalbard'"
    )
    parser.add_argument(
        "--svalbard-only", action="store_true",
        help="Only fetch Svalbard companies"
    )
    parser.add_argument(
        "--skip-websites", action="store_true",
        help="Skip proff.no website enrichment (faster)"
    )
    parser.add_argument(
        "--skip-sub-units", action="store_true",
        help="Only fetch main entities, skip sub-units (underenheter)"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from checkpoint (skip already-fetched NACE codes)"
    )
    parser.add_argument(
        "--output-csv", default=OUTPUT_CSV,
        help=f"Output CSV path (default: {OUTPUT_CSV})"
    )
    parser.add_argument(
        "--output-db", default=OUTPUT_DB,
        help=f"Output SQLite path (default: {OUTPUT_DB})"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  NORD-NORGE REISELIVSREGISTER — DATAINNHENTING")
    print("=" * 60)
    print(f"  Datakilde 1: Brønnøysundregistrene (open API)")
    print(f"  Datakilde 2: proff.no (nettstedberikelse)")
    print(f"  Målregion:   {'Svalbard' if args.svalbard_only else 'Nord-Norge + Svalbard'}")
    if args.county:
        print(f"  Fylkefilter: {args.county}")
    if args.nace:
        print(f"  NACE-filter: {args.nace}")
    print()

    # Load checkpoint if resuming
    state = load_checkpoint() if args.resume else {"fetched_nace_codes": [], "companies": []}
    all_companies = {c["org_nr"]: c for c in state.get("companies", []) if c.get("org_nr")}

    # Determine which NACE codes to fetch
    nace_codes = TRAVEL_NACE_CODES
    if args.nace:
        nace_codes = [c for c in TRAVEL_NACE_CODES if c.startswith(args.nace)]
        if not nace_codes:
            # Allow exact or partial match
            nace_codes = [args.nace]

    already_done = set(state.get("fetched_nace_codes", []))
    total_nace = len(nace_codes)

    for i, nace in enumerate(nace_codes, 1):
        if args.resume and nace in already_done:
            print(f"[{i}/{total_nace}] NACE {nace} — allerede hentet, hopper over")
            continue

        print(f"\n[{i}/{total_nace}] Henter NACE {nace}...")

        batch = fetch_all_for_nace(
            nace_code=nace,
            svalbard_only=args.svalbard_only,
            county_filter=args.county,
            include_sub_units=not args.skip_sub_units,
        )

        new_count = 0
        for company in batch:
            key = company["org_nr"] or company["name"]
            if key not in all_companies:
                all_companies[key] = company
                new_count += 1
            else:
                # Merge: keep website/phone if already enriched
                existing = all_companies[key]
                if not existing.get("website") and company.get("website"):
                    existing["website"] = company["website"]

        print(f"  → {len(batch)} hentet, {new_count} nye unike virksomheter")
        print(f"  → Totalt i minne: {len(all_companies)}")

        state["fetched_nace_codes"].append(nace)
        state["companies"] = list(all_companies.values())
        save_checkpoint(state)

        time.sleep(REQUEST_DELAY)

    companies = list(all_companies.values())
    print(f"\nHenting fullført. {len(companies)} unike virksomheter funnet.")

    # Enrich with proff.no website URLs
    if not args.skip_websites:
        # Only enrich active companies without a website
        to_enrich = [c for c in companies if c.get("status") == "active" and not c.get("website")]
        print(f"\n{len(to_enrich)} aktive virksomheter mangler nettsted — beriker fra proff.no...")
        enrich_from_proff(to_enrich)
        # Update main list
        enriched_map = {c["org_nr"]: c for c in to_enrich if c.get("org_nr")}
        for c in companies:
            if c["org_nr"] in enriched_map:
                c.update({
                    k: v for k, v in enriched_map[c["org_nr"]].items()
                    if v and not c.get(k)
                })

    # Save outputs
    final_companies = save_csv(companies, args.output_csv)
    build_sqlite(final_companies, args.output_db)
    print_db_summary(args.output_db)

    # Clean up checkpoint on success
    if os.path.exists(CHECKPOINT):
        os.remove(CHECKPOINT)

    print("\n" + "=" * 60)
    print(f"  FERDIG")
    print(f"  CSV:    {args.output_csv}")
    print(f"  SQLite: {args.output_db}")
    print("=" * 60)


if __name__ == "__main__":
    main()
