#!/usr/bin/env python3
"""
Build per-county CSV files of public sector organizations for all of Norway.

Uses existing nationwide CSV as base, enriches with Brønnøysundregistrene API,
adds scope tagging (Nasjonal/Lokal) and contact info, outputs per-county CSVs.

Usage:
    python build_county_csvs.py                    # Full run (all counties)
    python build_county_csvs.py --county Finnmark  # Single county
    python build_county_csvs.py --skip-api         # Split existing data only
    python build_county_csvs.py --dry-run          # Preview without writing
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from typing import Optional

import requests

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT_CSV = os.path.join(SCRIPT_DIR, "Virksomheter", "norge_offentlige_virksomheter_komplett (3).csv")
DEFAULT_COUNTIES_CSV = os.path.join(SCRIPT_DIR, "counties.csv")
DEFAULT_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "Virksomheter")

BRREG_BASE_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"
API_DELAY = 0.3  # seconds between requests
API_TIMEOUT = 30
API_MAX_RETRIES = 3

# Output CSV columns
OUTPUT_COLUMNS = [
    'Fylkesnummer', 'Fylkesnavn', 'Kommunenummer', 'Kommunenavn',
    'Virksomhet', 'Org nummer', 'Offisiell nettside',
    'Epost', 'Telefon',
    'Scope', 'UU Status', 'Antall brudd (av 48)', 'Sist oppdatert'
]

# --- Organization form filtering ---
SKIP_ORG_FORMS = {'ORGL'}  # Internal organizational divisions

# Words that should stay uppercase in org names
KEEP_UPPER = {
    'KF', 'IKS', 'AS', 'HF', 'RHF', 'SF', 'NAV', 'NTNU', 'SA', 'ANS',
    'DA', 'NHH', 'NMBU', 'UIT', 'NITO', 'NRK', 'NSD', 'NFR', 'NVE',
    'DSB', 'NSB', 'NFF', 'OUS', 'NTNU', 'USN', 'UIS', 'UIB', 'UIA',
    'NORD', 'SIVA', 'ENOVA', 'II', 'III', 'IV', 'A/S', 'BA',
}

# --- Scope classification ---
NATIONAL_KEYWORDS = [
    'direktorat', 'departement', 'tilsyn', 'riksrevisjon',
    'sivilombud', 'stortinget', 'regjeringen', 'kongehus',
    'nasjonalmuseet', 'nasjonalbiblioteket', 'nasjonalteatret',
    'norges bank', 'politidirektorat', 'domstoladministrasjon',
    'kripos', 'økokrim', 'politihøgskolen',
    'helse sør-øst rhf', 'helse vest rhf', 'helse midt-norge rhf',
    'helse nord rhf',
    'folkehelseinstituttet', 'mattilsynet',
    'innovasjon norge', 'forskningsrådet', 'enova',
    'statens vegvesen', 'jernbanedirektoratet', 'avinor',
    'vinmonopolet', 'norsk tipping', 'statnett',
    'statkraft', 'statsbygg', 'statskog',
    'nasjonal kommunikasjonsmyndighet', 'arbeidstilsynet',
    'brønnøysundregistrene', 'kartverket', 'konkurransetilsynet',
    'datatilsynet', 'forbrukertilsynet', 'lotteritilsynet',
    'medietilsynet', 'sjøfartsdirektoratet', 'oljedirektoratet',
    'havtilsynet', 'finanstilsynet', 'helsetilsynet',
    'utdanningsdirektoratet', 'bufdir', 'imdi', 'udi',
    'lånekassen', 'husbanken', 'toll', 'skatteetaten',
    'patentstyret', 'forsvarsbygg', 'forsvarsdepartement',
]

NATIONAL_BRANSJE = {
    'Statlig forvaltning', 'Statlig foretak', 'Tilskuddsforvalter',
    'Departement', 'Direktorat',
}

NATIONAL_SCOPE_PATTERNS = [
    r'statsforvalter',
    r'politidistrikt',
    r'lagmannsrett',
    r'høyesterett',
    r'riksadvokat',
    r'\brhf\b',
    r'universitetet i',
    r'^uit\b',
    r'^ntnu\b',
    r'^nmbu\b',
    r'^nhh\b',
    r'^usn\b',
    r'^oslomet\b',
]


# ============================================================
# API Client
# ============================================================

class BrregClient:
    """Client for Brønnøysundregistrene Enhetsregisteret API."""

    def __init__(self, delay=API_DELAY):
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'WCAG-Checker-CountyBuilder/1.0'
        })
        self.delay = delay
        self._last_request_time = 0
        self.total_requests = 0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    def _get(self, params: dict) -> Optional[dict]:
        """Make a single API request with retries."""
        for attempt in range(API_MAX_RETRIES):
            self._rate_limit()
            try:
                resp = self.session.get(BRREG_BASE_URL, params=params, timeout=API_TIMEOUT)
                self.total_requests += 1
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code in (429, 500, 502, 503):
                    wait = (attempt + 1) * 2
                    time.sleep(wait)
                    continue
                return None
            except (requests.exceptions.RequestException, json.JSONDecodeError):
                if attempt == API_MAX_RETRIES - 1:
                    return None
                time.sleep((attempt + 1) * 2)
        return None

    def _paginated_fetch(self, params: dict) -> list:
        """Fetch all pages of results."""
        all_results = []
        page = 0
        while True:
            params['page'] = page
            data = self._get(params)
            if not data:
                break
            embedded = data.get('_embedded', {})
            entities = embedded.get('enheter', [])
            if not entities:
                break
            all_results.extend(entities)
            page_info = data.get('page', {})
            total_pages = page_info.get('totalPages', 1)
            if page + 1 >= total_pages:
                break
            page += 1
        return all_results

    def get_public_orgs(self, kommunenummer: str) -> list:
        """Get all public sector orgs for a municipality using two strategies."""
        # Strategy A: by institutional sector codes (state + municipal admin)
        by_sector = self._paginated_fetch({
            'kommunenummer': kommunenummer,
            'institusjonellSektorkode': '6100,6500',
            'size': 100,
        })

        # Strategy B: by organization form codes
        by_form = self._paginated_fetch({
            'kommunenummer': kommunenummer,
            'organisasjonsform': 'KOMM,FYLK,KF,FKF,IKS,SF,KIRK',
            'size': 100,
        })

        # Merge and deduplicate by org number
        seen = {}
        for entity in by_sector + by_form:
            orgnr = entity.get('organisasjonsnummer')
            if orgnr and orgnr not in seen:
                seen[orgnr] = entity
        return list(seen.values())

    def get_single_entity(self, orgnr: str) -> Optional[dict]:
        """Fetch a single entity by org number (for contact info enrichment)."""
        self._rate_limit()
        try:
            resp = self.session.get(f"{BRREG_BASE_URL}/{orgnr}", timeout=API_TIMEOUT)
            self.total_requests += 1
            if resp.status_code == 200:
                return resp.json()
        except (requests.exceptions.RequestException, json.JSONDecodeError):
            pass
        return None


# ============================================================
# Helper functions
# ============================================================

def normalize_org_nr(org_nr: str) -> str:
    """Strip spaces and clean org number."""
    if not org_nr:
        return ''
    return str(org_nr).replace(' ', '').replace('\xa0', '').strip()


def normalize_url(url: str) -> str:
    """Ensure URL has https:// prefix."""
    if not url or not url.strip():
        return ''
    url = url.strip()
    if url.startswith('http://') or url.startswith('https://'):
        return url
    return 'https://' + url


def normalize_name(name: str) -> str:
    """Convert ALL CAPS name to title case, keeping abbreviations uppercase."""
    if not name:
        return ''
    # If already mixed case, keep as-is
    if name != name.upper():
        return name

    words = name.split()
    result = []
    for word in words:
        clean = word.strip('(),.-/')
        if clean.upper() in KEEP_UPPER:
            result.append(word)  # keep original casing
        elif word.startswith('(') and word.endswith(')'):
            # Parenthesized abbreviations stay uppercase
            result.append(word)
        elif len(clean) <= 2 and clean.isalpha():
            # Short words like "OG", "I", "AV" -> lowercase in Norwegian
            result.append(word.lower())
        else:
            result.append(word.capitalize())
        # Fix common Norwegian title case issues
    text = ' '.join(result)
    # "Og" at start of sentence should be lowercase
    text = re.sub(r'\bOg\b', 'og', text)
    text = re.sub(r'\bI\b', 'i', text)
    text = re.sub(r'\bFor\b', 'for', text)
    text = re.sub(r'\bAv\b', 'av', text)
    text = re.sub(r'\bMed\b', 'med', text)
    text = re.sub(r'\bTil\b', 'til', text)
    # But capitalize first word
    if text:
        text = text[0].upper() + text[1:]
    return text


def should_include_entity(entity: dict) -> bool:
    """Filter out entities we don't want."""
    org_form = entity.get('organisasjonsform', {}).get('kode', '')
    if org_form in SKIP_ORG_FORMS:
        return False
    if entity.get('konkurs') or entity.get('underAvvikling'):
        return False
    if entity.get('underTvangsavviklingEllerTvangsopplosning'):
        return False
    # Skip individual church parishes, keep fellesråd
    name_upper = (entity.get('navn') or '').upper()
    if org_form == 'KIRK':
        if 'FELLESRÅD' not in name_upper and 'FELLESRAD' not in name_upper:
            return False
    return True


def classify_scope(name: str, bransje: str = '') -> str:
    """Classify an organization as Nasjonal or Lokal."""
    name_lower = name.lower()

    # Check bransje
    if bransje in NATIONAL_BRANSJE:
        return 'Nasjonal'

    # Check keyword matches
    for keyword in NATIONAL_KEYWORDS:
        if keyword in name_lower:
            return 'Nasjonal'

    # Check regex patterns
    for pattern in NATIONAL_SCOPE_PATTERNS:
        if re.search(pattern, name_lower):
            return 'Nasjonal'

    return 'Lokal'


def entity_to_row(entity: dict, county_number: str, county_name: str) -> dict:
    """Convert a BRREG API entity to a CSV row dict."""
    addr = entity.get('forretningsadresse', {}) or entity.get('postadresse', {}) or {}

    return {
        'Fylkesnummer': county_number,
        'Fylkesnavn': county_name,
        'Kommunenummer': addr.get('kommunenummer', ''),
        'Kommunenavn': (addr.get('kommune') or '').title(),
        'Virksomhet': normalize_name(entity.get('navn', '')),
        'Org nummer': str(entity.get('organisasjonsnummer', '')),
        'Offisiell nettside': normalize_url(entity.get('hjemmeside', '')),
        'Epost': entity.get('epostadresse', ''),
        'Telefon': entity.get('telefon', ''),
        'Scope': classify_scope(entity.get('navn', '')),
        'UU Status': 'Ikke testet',
        'Antall brudd (av 48)': '',
        'Sist oppdatert': '',
    }


# ============================================================
# Data loading
# ============================================================

def load_existing_data(csv_path: str) -> dict:
    """Load the existing nationwide CSV into a dict keyed by normalized org number.
    Returns {org_nr: row_dict, ...} plus a list of rows without org numbers.
    """
    by_orgnr = {}
    no_orgnr = []

    if not os.path.exists(csv_path):
        print(f"WARNING: Input CSV not found: {csv_path}")
        return by_orgnr, no_orgnr

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            org_nr = normalize_org_nr(row.get('Org nummer', ''))
            if org_nr and org_nr.isdigit() and len(org_nr) == 9:
                by_orgnr[org_nr] = row
            else:
                no_orgnr.append(row)

    return by_orgnr, no_orgnr


def load_counties_mapping(csv_path: str) -> dict:
    """Load counties.csv into {county_number: {name, municipalities: [{nr, name, url}]}}.
    """
    counties = {}

    if not os.path.exists(csv_path):
        print(f"WARNING: Counties CSV not found: {csv_path}")
        return counties

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            c_nr = row.get('County Number', '').strip()
            c_name = row.get('County Name', '').strip()
            m_nr = row.get('Municipality Number', '').strip()
            m_name = row.get('Municipality Name', '').strip()
            m_url = row.get('Official Website', '').strip()

            if c_nr not in counties:
                counties[c_nr] = {
                    'name': c_name,
                    'municipalities': []
                }
            counties[c_nr]['municipalities'].append({
                'number': m_nr,
                'name': m_name,
                'url': m_url,
            })

    return counties


def group_existing_by_county(existing_by_orgnr: dict, existing_no_orgnr: list) -> dict:
    """Group existing data by county number."""
    by_county = defaultdict(list)

    for org_nr, row in existing_by_orgnr.items():
        county_nr = row.get('Fylkesnummer', '').strip()
        if county_nr:
            by_county[county_nr].append(row)

    for row in existing_no_orgnr:
        county_nr = row.get('Fylkesnummer', '').strip()
        if county_nr:
            by_county[county_nr].append(row)

    return dict(by_county)


# ============================================================
# Enrichment
# ============================================================

def enrich_contact_info(client: BrregClient, org_nr: str) -> dict:
    """Fetch contact info for a single org from API."""
    entity = client.get_single_entity(org_nr)
    if entity:
        return {
            'Epost': entity.get('epostadresse', ''),
            'Telefon': entity.get('telefon', ''),
            'hjemmeside': entity.get('hjemmeside', ''),
        }
    return {}


def convert_existing_row(row: dict, county_nr: str, county_name: str) -> dict:
    """Convert an existing CSV row to the output format."""
    # Map from existing columns (which may differ slightly)
    virksomhet = row.get('Virksomhet', '').strip()
    website = normalize_url(row.get('Offisiell nettside', '').strip())
    bransje = row.get('Bransje', '').strip()

    return {
        'Fylkesnummer': county_nr,
        'Fylkesnavn': county_name,
        'Kommunenummer': row.get('Kommunenummer', '').strip(),
        'Kommunenavn': row.get('Kommunenavn', '').strip(),
        'Virksomhet': virksomhet,
        'Org nummer': normalize_org_nr(row.get('Org nummer', '')),
        'Offisiell nettside': website,
        'Epost': row.get('Epost', ''),
        'Telefon': row.get('Telefon', ''),
        'Scope': classify_scope(virksomhet, bransje),
        'UU Status': row.get('UU Status', 'Ikke testet').strip(),
        'Antall brudd (av 48)': row.get('Antall brudd', row.get('Antall brudd (av 48)', '')).strip(),
        'Sist oppdatert': row.get('Sist oppdatert', '').strip(),
    }


def _name_key(name: str) -> str:
    """Normalize a name for deduplication comparison."""
    s = name.lower().strip()
    # Remove common suffixes/prefixes for matching
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'[^\w\s]', '', s)
    return s


def _deduplicate_rows(rows_dict: dict) -> dict:
    """Remove near-duplicate entries (same normalized name + same municipality).
    When duplicates found, keep the one with more data (org number, URL, contact).
    """
    # Group by (normalized_name, kommunenummer)
    groups = defaultdict(list)
    for key, row in rows_dict.items():
        name_k = _name_key(row.get('Virksomhet', ''))
        muni = row.get('Kommunenummer', '').strip()
        groups[(name_k, muni)].append((key, row))

    result = {}
    for (name_k, muni), entries in groups.items():
        if len(entries) == 1:
            result[entries[0][0]] = entries[0][1]
        else:
            # Pick the best entry: prefer one with org number, URL, and contact info
            def score(item):
                k, r = item
                s = 0
                org = r.get('Org nummer', '')
                if org and org.isdigit() and len(org) == 9:
                    s += 10
                if r.get('Offisiell nettside'):
                    s += 5
                if r.get('Epost'):
                    s += 3
                if r.get('Telefon'):
                    s += 2
                return s
            entries.sort(key=score, reverse=True)
            best_key, best_row = entries[0]
            # Merge data from other entries into best
            for other_key, other_row in entries[1:]:
                if not best_row.get('Epost') and other_row.get('Epost'):
                    best_row['Epost'] = other_row['Epost']
                if not best_row.get('Telefon') and other_row.get('Telefon'):
                    best_row['Telefon'] = other_row['Telefon']
                if not best_row.get('Offisiell nettside') and other_row.get('Offisiell nettside'):
                    best_row['Offisiell nettside'] = other_row['Offisiell nettside']
                org_best = best_row.get('Org nummer', '')
                org_other = other_row.get('Org nummer', '')
                if not (org_best and org_best.isdigit()) and org_other and org_other.isdigit():
                    best_row['Org nummer'] = org_other
            result[best_key] = best_row

    return result


def build_county_data(
    county_nr: str,
    county_name: str,
    existing_rows: list,
    municipalities: list,
    client: Optional[BrregClient],
    existing_by_orgnr: dict,
    muni_to_county: dict,
) -> tuple:
    """Build the complete dataset for a single county.
    Returns (rows, stats_dict).
    """
    merged = {}  # keyed by org_nr or fallback key
    stats = {'existing': 0, 'api_new': 0, 'contact_enriched': 0}

    # Build set of municipality numbers belonging to this county
    county_muni_nrs = {m['number'] for m in municipalities}

    # Step 1: Add all existing rows for this county
    # Trust the Fylkesnummer from the existing CSV (don't cross-county filter existing
    # data, as it may use old municipality numbers from the 2020-2024 merger period)
    for row in existing_rows:
        org_nr = normalize_org_nr(row.get('Org nummer', ''))
        converted = convert_existing_row(row, county_nr, county_name)
        row_muni = converted.get('Kommunenummer', '').strip()

        if org_nr and org_nr.isdigit() and len(org_nr) == 9:
            merged[org_nr] = converted
        else:
            key = f"_no_orgnr_{_name_key(converted['Virksomhet'])}_{row_muni}"
            merged[key] = converted
        stats['existing'] += 1

    # Step 2: Enrich from BRREG API
    if client and municipalities:
        for muni in municipalities:
            muni_nr = muni['number']
            if not muni_nr:
                continue

            entities = client.get_public_orgs(muni_nr)
            for entity in entities:
                if not should_include_entity(entity):
                    continue

                # Skip API entities whose business address is in a different county
                addr = entity.get('forretningsadresse', {}) or {}
                entity_muni = addr.get('kommunenummer', '')
                if entity_muni and entity_muni not in county_muni_nrs:
                    other_county = muni_to_county.get(entity_muni)
                    if other_county and other_county != county_nr:
                        continue

                org_nr = str(entity.get('organisasjonsnummer', ''))
                if org_nr not in merged:
                    new_row = entity_to_row(entity, county_nr, county_name)
                    # Override municipality to the queried one if address is in different county
                    if entity_muni not in county_muni_nrs:
                        new_row['Kommunenummer'] = muni_nr
                        new_row['Kommunenavn'] = muni['name']
                    merged[org_nr] = new_row
                    stats['api_new'] += 1
                else:
                    # Entity already exists: enrich contact info if missing
                    existing = merged[org_nr]
                    if not existing.get('Epost') and entity.get('epostadresse'):
                        existing['Epost'] = entity.get('epostadresse', '')
                        stats['contact_enriched'] += 1
                    if not existing.get('Telefon') and entity.get('telefon'):
                        existing['Telefon'] = entity.get('telefon', '')
                    if not existing.get('Offisiell nettside') and entity.get('hjemmeside'):
                        existing['Offisiell nettside'] = normalize_url(entity.get('hjemmeside', ''))

    # Step 3: For existing rows that still lack contact info, fetch from API individually
    if client:
        rows_needing_contact = [
            (k, v) for k, v in merged.items()
            if not v.get('Epost') and k.isdigit() and len(k) == 9
        ]
        # Limit to avoid too many API calls (contact enrichment is secondary)
        for org_nr, row in rows_needing_contact[:200]:
            contact = enrich_contact_info(client, org_nr)
            if contact.get('Epost'):
                row['Epost'] = contact['Epost']
                stats['contact_enriched'] += 1
            if contact.get('Telefon'):
                row['Telefon'] = contact['Telefon']
            if not row.get('Offisiell nettside') and contact.get('hjemmeside'):
                row['Offisiell nettside'] = normalize_url(contact['hjemmeside'])

    # Step 4: Deduplicate near-identical entries
    merged = _deduplicate_rows(merged)

    # Sort by Kommunenummer then Virksomhet
    rows = sorted(
        merged.values(),
        key=lambda r: (r.get('Kommunenummer', ''), r.get('Virksomhet', ''))
    )

    return rows, stats


def write_county_csv(output_dir: str, county_name: str, rows: list, dry_run: bool = False):
    """Write a per-county CSV file."""
    # Sanitize filename
    safe_name = county_name.replace(' ', '_').replace('ø', 'o').replace('Ø', 'O')
    safe_name = re.sub(r'[^\w\-]', '', safe_name)
    filename = f"{county_name}Public.csv"
    filepath = os.path.join(output_dir, filename)

    if dry_run:
        print(f"  [DRY RUN] Would write {len(rows)} rows to {filename}")
        return filepath

    os.makedirs(output_dir, exist_ok=True)

    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    return filepath


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='Build per-county CSVs of public sector organizations for Norway'
    )
    parser.add_argument('--county', type=str, help='Process only a specific county (by name)')
    parser.add_argument('--skip-api', action='store_true', help='Skip BRREG API enrichment')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing files')
    parser.add_argument('--api-delay', type=float, default=API_DELAY,
                        help=f'Seconds between API requests (default: {API_DELAY})')
    parser.add_argument('--input-csv', type=str, default=DEFAULT_INPUT_CSV,
                        help='Path to nationwide organizations CSV')
    parser.add_argument('--counties-csv', type=str, default=DEFAULT_COUNTIES_CSV,
                        help='Path to counties/municipalities CSV')
    parser.add_argument('--output-dir', type=str, default=DEFAULT_OUTPUT_DIR,
                        help='Output directory for per-county CSVs')
    args = parser.parse_args()

    start_time = time.time()
    print("=" * 70)
    print("  Norway Public Sector Organization CSV Builder")
    print("=" * 70)
    print(f"  Input CSV:    {args.input_csv}")
    print(f"  Counties CSV: {args.counties_csv}")
    print(f"  Output dir:   {args.output_dir}")
    print(f"  API:          {'DISABLED' if args.skip_api else 'ENABLED'}")
    print(f"  Dry run:      {'YES' if args.dry_run else 'NO'}")
    if args.county:
        print(f"  County filter: {args.county}")
    print("=" * 70)
    print()

    # Step 1: Load data
    print("[1/4] Loading existing data...")
    existing_by_orgnr, existing_no_orgnr = load_existing_data(args.input_csv)
    print(f"  Loaded {len(existing_by_orgnr)} orgs with org numbers, {len(existing_no_orgnr)} without")

    print("[2/4] Loading county/municipality mapping...")
    counties_map = load_counties_mapping(args.counties_csv)
    print(f"  Loaded {len(counties_map)} counties with {sum(len(c['municipalities']) for c in counties_map.values())} municipalities")

    # Group existing data by county
    existing_by_county = group_existing_by_county(existing_by_orgnr, existing_no_orgnr)

    # Build complete county list (from both sources)
    all_counties = {}
    for c_nr, c_data in counties_map.items():
        all_counties[c_nr] = c_data['name']
    # Add counties from existing data that might not be in counties.csv (e.g., Svalbard)
    for c_nr, rows in existing_by_county.items():
        if c_nr not in all_counties and rows:
            all_counties[c_nr] = rows[0].get('Fylkesnavn', f'County {c_nr}')

    # Filter to single county if requested
    if args.county:
        matching = {k: v for k, v in all_counties.items()
                    if v.lower() == args.county.lower()}
        if not matching:
            # Try partial match
            matching = {k: v for k, v in all_counties.items()
                        if args.county.lower() in v.lower()}
        if not matching:
            print(f"ERROR: County '{args.county}' not found. Available counties:")
            for nr, name in sorted(all_counties.items()):
                print(f"  {nr}: {name}")
            sys.exit(1)
        all_counties = matching

    print(f"\n  Processing {len(all_counties)} counties:")
    for nr in sorted(all_counties.keys()):
        print(f"    {nr}: {all_counties[nr]}")
    print()

    # Step 2: Initialize API client
    client = None
    if not args.skip_api:
        print("[3/4] Initializing BRREG API client...")
        client = BrregClient(delay=args.api_delay)
        total_munis = sum(
            len(counties_map.get(c_nr, {}).get('municipalities', []))
            for c_nr in all_counties
        )
        est_time = total_munis * 2 * (args.api_delay + 0.5)
        print(f"  Will query {total_munis} municipalities (~{est_time/60:.1f} min estimated)")
    else:
        print("[3/4] Skipping API enrichment (--skip-api)")
    print()

    # Build municipality-to-county mapping for cross-county filtering
    muni_to_county = {}
    for c_nr, c_data in counties_map.items():
        for muni in c_data.get('municipalities', []):
            muni_to_county[muni['number']] = c_nr

    # Step 3: Process each county
    print("[4/4] Building per-county CSVs...")
    print()

    all_stats = {}
    total_rows = 0

    for idx, c_nr in enumerate(sorted(all_counties.keys()), 1):
        c_name = all_counties[c_nr]
        existing_rows = existing_by_county.get(c_nr, [])
        municipalities = counties_map.get(c_nr, {}).get('municipalities', [])

        print(f"  [{idx}/{len(all_counties)}] {c_name} (fylke {c_nr}): "
              f"{len(existing_rows)} existing, {len(municipalities)} municipalities...", end='', flush=True)

        rows, stats = build_county_data(
            county_nr=c_nr,
            county_name=c_name,
            existing_rows=existing_rows,
            municipalities=municipalities,
            client=client,
            existing_by_orgnr=existing_by_orgnr,
            muni_to_county=muni_to_county,
        )

        filepath = write_county_csv(args.output_dir, c_name, rows, dry_run=args.dry_run)
        stats['total'] = len(rows)
        stats['with_url'] = sum(1 for r in rows if r.get('Offisiell nettside'))
        stats['with_email'] = sum(1 for r in rows if r.get('Epost'))
        stats['with_phone'] = sum(1 for r in rows if r.get('Telefon'))
        all_stats[c_name] = stats
        total_rows += len(rows)

        print(f" -> {len(rows)} total ({stats['api_new']} new from API, "
              f"{stats['contact_enriched']} contacts enriched)")

    # Print summary
    elapsed = time.time() - start_time
    print()
    print("=" * 100)
    print("  SUMMARY")
    print("=" * 100)
    print(f"{'County':<25} {'Existing':>8} {'API New':>8} {'Total':>8} "
          f"{'With URL':>9} {'With Email':>10} {'With Phone':>11}")
    print("-" * 100)

    for c_name in sorted(all_stats.keys()):
        s = all_stats[c_name]
        print(f"{c_name:<25} {s['existing']:>8} {s['api_new']:>8} {s['total']:>8} "
              f"{s['with_url']:>9} {s['with_email']:>10} {s['with_phone']:>11}")

    print("-" * 100)
    total_existing = sum(s['existing'] for s in all_stats.values())
    total_api_new = sum(s['api_new'] for s in all_stats.values())
    total_urls = sum(s['with_url'] for s in all_stats.values())
    total_emails = sum(s['with_email'] for s in all_stats.values())
    total_phones = sum(s['with_phone'] for s in all_stats.values())
    print(f"{'TOTAL':<25} {total_existing:>8} {total_api_new:>8} {total_rows:>8} "
          f"{total_urls:>9} {total_emails:>10} {total_phones:>11}")
    print()
    print(f"  Time elapsed: {elapsed:.1f} seconds")
    if client:
        print(f"  API requests made: {client.total_requests}")
    print(f"  Output directory: {args.output_dir}")
    print()

    # Save summary JSON
    if not args.dry_run:
        summary = {
            'generated': datetime.now().isoformat(),
            'total_organizations': total_rows,
            'total_counties': len(all_stats),
            'counties': all_stats,
        }
        summary_path = os.path.join(args.output_dir, '_enrichment_summary.json')
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"  Summary saved to: {summary_path}")

    print("\nDone!")


if __name__ == '__main__':
    main()
