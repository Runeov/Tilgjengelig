#!/usr/bin/env python3
"""
Nord-Norge Travel Company Database — Search & Explore CLI
==========================================================
Interactive command-line tool for searching and exploring the
nordnorge_travel.db SQLite database built by fetch_nordnorge_travel.py.

Features:
  - Full-text search across all fields (FTS5)
  - Filter by county, municipality, NACE, status, has_website
  - Export search results to CSV or JSON
  - Summary statistics tables
  - Feed results directly to batch_scan_finnmark_travel.py

Usage:
    python search_travel_db.py                          # Interactive mode
    python search_travel_db.py --search "nordlys"       # Full-text search
    python search_travel_db.py --county Finnmark        # By county
    python search_travel_db.py --municipality Alta      # By municipality
    python search_travel_db.py --nace 79                # Tour operators only
    python search_travel_db.py --no-website             # Missing website
    python search_travel_db.py --svalbard               # Svalbard only
    python search_travel_db.py --summary                # Print statistics
    python search_travel_db.py --export results.csv     # Export to CSV
    python search_travel_db.py --export results.json    # Export to JSON
    python search_travel_db.py --to-scan-csv            # Export for scanner
"""

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from typing import Optional

DEFAULT_DB = "nordnorge_travel.db"


# ─────────────────────────────────────────────────────────────────────────────
# Database connection helpers
# ─────────────────────────────────────────────────────────────────────────────

def open_db(path: str) -> sqlite3.Connection:
    if not os.path.exists(path):
        print(f"Database ikke funnet: {path}")
        print("Kjør først: python fetch_nordnorge_travel.py")
        sys.exit(1)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(zip(row.keys(), row))


# ─────────────────────────────────────────────────────────────────────────────
# Query builders
# ─────────────────────────────────────────────────────────────────────────────

def build_query(
    search:       Optional[str] = None,
    county:       Optional[str] = None,
    municipality: Optional[str] = None,
    nace:         Optional[str] = None,
    status:       Optional[str] = "active",
    no_website:   bool = False,
    has_website:  bool = False,
    svalbard:     bool = False,
    org_form:     Optional[str] = None,
    limit:        int = 500,
    offset:       int = 0,
) -> tuple[str, list]:
    """Build SQL query and params from filter arguments."""

    if search:
        # FTS search
        base = """
            SELECT c.*
            FROM companies c
            JOIN companies_fts fts ON c.id = fts.rowid
            WHERE companies_fts MATCH ?
        """
        params = [search]
    else:
        base = "SELECT * FROM companies WHERE 1=1"
        params = []

    filters = []

    if county:
        filters.append("LOWER(county) LIKE ?")
        params.append(f"%{county.lower()}%")

    if municipality:
        filters.append("LOWER(municipality) LIKE ?")
        params.append(f"%{municipality.lower()}%")

    if nace:
        filters.append("nace_code LIKE ?")
        params.append(f"{nace}%")

    if status:
        filters.append("status = ?")
        params.append(status)

    if no_website:
        filters.append("(website IS NULL OR website = '')")

    if has_website:
        filters.append("website != '' AND website IS NOT NULL")

    if svalbard:
        filters.append("(county LIKE '%Svalbard%' OR municipality LIKE '%Svalbard%' OR postal_place LIKE '%LONGYEARBYEN%')")

    if org_form:
        filters.append("org_form = ?")
        params.append(org_form.upper())

    if filters:
        if search:
            base += " AND " + " AND ".join(filters)
        else:
            base += " AND " + " AND ".join(filters)

    base += f" ORDER BY county, municipality, name LIMIT {int(limit)} OFFSET {int(offset)}"
    return base, params


def count_query(sql: str, params: list, conn: sqlite3.Connection) -> int:
    """Get total count for a query (without LIMIT/OFFSET)."""
    count_sql = re.sub(
        r'SELECT .+? FROM',
        'SELECT COUNT(*) FROM',
        sql, count=1, flags=re.DOTALL
    )
    count_sql = re.sub(r'ORDER BY .+$', '', count_sql, flags=re.DOTALL)
    count_sql = re.sub(r'LIMIT \d+ OFFSET \d+', '', count_sql)
    try:
        return conn.execute(count_sql, params).fetchone()[0]
    except Exception:
        return -1


# ─────────────────────────────────────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────────────────────────────────────

def _col(text: str, width: int) -> str:
    text = str(text or "")
    if len(text) > width:
        return text[:width - 1] + "…"
    return text.ljust(width)


def print_table(rows: list[dict], columns: list[tuple]):
    """
    Print a formatted table.
    columns = [(field_name, header, width), ...]
    """
    header = "  ".join(_col(h, w) for _, h, w in columns)
    sep    = "  ".join("─" * w for _, _, w in columns)
    print(header)
    print(sep)
    for row in rows:
        line = "  ".join(_col(row.get(f, ""), w) for f, _, w in columns)
        print(line)


def print_results(rows: list[dict], total: int, page: int = 1, page_size: int = 30):
    """Print a paginated results table."""
    shown = len(rows)
    print(f"\n  Viser {shown} av {total} treff  (side {page})\n")

    print_table(rows, [
        ("org_nr",           "Org.nr",       11),
        ("name",             "Navn",         36),
        ("nace_code",        "NACE",          8),
        ("municipality",     "Kommune",      18),
        ("county",           "Fylke",        20),
        ("status",           "Status",        9),
        ("website",          "Nettsted",     34),
    ])
    print()


def print_summary(conn: sqlite3.Connection):
    """Print database statistics."""
    total   = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    active  = conn.execute("SELECT COUNT(*) FROM companies WHERE status='active'").fetchone()[0]
    web     = conn.execute("SELECT COUNT(*) FROM companies WHERE website!=''").fetchone()[0]
    svalbrd = conn.execute(
        "SELECT COUNT(*) FROM companies WHERE county LIKE '%Svalbard%' "
        "OR postal_place LIKE '%LONGYEARBYEN%'"
    ).fetchone()[0]

    print("\n" + "═" * 64)
    print("  DATABASEOVERSIKT — Nord-Norge Reiselivsregister")
    print("═" * 64)
    print(f"  Totalt virksomheter:   {total:>6}")
    print(f"  Aktive:                {active:>6}")
    print(f"  Har nettsted:          {web:>6}  ({web*100//max(total,1)}%)")
    print(f"  Svalbard:              {svalbrd:>6}")
    print(f"  Mangler nettsted:      {total - web:>6}  ({(total-web)*100//max(total,1)}%)")

    print("\n  Etter fylke:")
    print_table(
        [row_to_dict(r) for r in conn.execute("SELECT * FROM summary_by_county")],
        [
            ("county",       "Fylke",         26),
            ("total",        "Totalt",         7),
            ("active",       "Aktive",         7),
            ("has_website",  "M/nettsted",    11),
            ("main_entities","Hovedenheter",  14),
        ]
    )

    print("\n  Etter NACE-kategori:")
    print_table(
        [row_to_dict(r) for r in conn.execute("SELECT * FROM summary_by_nace")],
        [
            ("nace_code",        "NACE",    9),
            ("nace_description", "Beskrivelse", 44),
            ("total",            "Totalt",   7),
            ("active",           "Aktive",   7),
        ]
    )
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Export helpers
# ─────────────────────────────────────────────────────────────────────────────

def export_csv(rows: list[dict], path: str):
    if not rows:
        print("Ingen rader å eksportere.")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Eksportert {len(rows)} rader til: {path}")


def export_json(rows: list[dict], path: str):
    if not rows:
        print("Ingen rader å eksportere.")
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    print(f"Eksportert {len(rows)} rader til: {path}")


def export_for_scanner(rows: list[dict], path: str):
    """
    Export a CSV in FinnmarkTravel.csv format so batch_scan_finnmark_travel.py
    can consume it directly. Only includes companies with a known website.
    """
    scannable = [r for r in rows if r.get("website")]
    not_scannable = len(rows) - len(scannable)

    if not_scannable:
        print(f"  OBS: {not_scannable} virksomheter uten nettsted er utelatt fra skannbar CSV")

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "category_id", "category_name", "company_id", "company_name",
            "url", "org_nr", "municipality", "region", "notes"
        ])
        for i, r in enumerate(scannable, 1):
            writer.writerow([
                r.get("nace_code", ""),
                r.get("nace_description", "Reiseliv"),
                str(i).zfill(4),
                r.get("name", ""),
                r.get("website", ""),
                r.get("org_nr", ""),
                r.get("municipality", ""),
                r.get("county", ""),
                f"Ansatte: {r.get('employees','')} | Grunnlagt: {r.get('founded_year','')}",
            ])

    print(f"Skannbar CSV lagret: {path} ({len(scannable)} virksomheter med nettsted)")


# ─────────────────────────────────────────────────────────────────────────────
# Interactive mode
# ─────────────────────────────────────────────────────────────────────────────

def interactive_mode(conn: sqlite3.Connection):
    """Simple interactive REPL for exploring the database."""
    print("\n" + "═" * 60)
    print("  Nord-Norge Reiselivsregister — Søkemodus")
    print("═" * 60)
    print("  Kommandoer:")
    print("    <søkeord>          Full-tekst søk")
    print("    fylke <navn>       Filtrer på fylke")
    print("    kommune <navn>     Filtrer på kommune")
    print("    nace <kode>        Filtrer på NACE-kode (f.eks. 79)")
    print("    ingen-nettsted     Vis virksomheter uten nettsted")
    print("    svalbard           Vis bare Svalbard")
    print("    sammendrag         Vis statistikk")
    print("    eksport <fil.csv>  Eksporter siste søk")
    print("    skann <fil.csv>    Eksporter til skannerformat")
    print("    avslutt            Avslutt")
    print()

    last_rows = []
    page_size = 30

    while True:
        try:
            raw = input("  db> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAvslutter.")
            break

        if not raw:
            continue

        parts = raw.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("avslutt", "exit", "quit", "q"):
            break

        elif cmd == "sammendrag":
            print_summary(conn)

        elif cmd == "fylke":
            sql, params = build_query(county=arg)
            rows = [row_to_dict(r) for r in conn.execute(sql, params)]
            total = count_query(sql, params, conn)
            last_rows = rows
            print_results(rows[:page_size], total)

        elif cmd == "kommune":
            sql, params = build_query(municipality=arg)
            rows = [row_to_dict(r) for r in conn.execute(sql, params)]
            total = count_query(sql, params, conn)
            last_rows = rows
            print_results(rows[:page_size], total)

        elif cmd == "nace":
            sql, params = build_query(nace=arg)
            rows = [row_to_dict(r) for r in conn.execute(sql, params)]
            total = count_query(sql, params, conn)
            last_rows = rows
            print_results(rows[:page_size], total)

        elif cmd == "ingen-nettsted":
            sql, params = build_query(no_website=True)
            rows = [row_to_dict(r) for r in conn.execute(sql, params)]
            total = count_query(sql, params, conn)
            last_rows = rows
            print_results(rows[:page_size], total)

        elif cmd == "svalbard":
            sql, params = build_query(svalbard=True)
            rows = [row_to_dict(r) for r in conn.execute(sql, params)]
            total = count_query(sql, params, conn)
            last_rows = rows
            print_results(rows[:page_size], total)

        elif cmd == "eksport":
            if not arg:
                print("  Bruk: eksport <filnavn.csv eller .json>")
                continue
            if arg.endswith(".json"):
                export_json(last_rows, arg)
            else:
                export_csv(last_rows, arg)

        elif cmd == "skann":
            if not arg:
                print("  Bruk: skann <filnavn.csv>")
                continue
            export_for_scanner(last_rows, arg)

        else:
            # Full-text search
            query_text = raw
            try:
                sql, params = build_query(search=query_text)
                rows = [row_to_dict(r) for r in conn.execute(sql, params)]
                total = count_query(sql, params, conn)
                last_rows = rows
                print_results(rows[:page_size], total)
            except sqlite3.OperationalError as e:
                print(f"  Søkefeil: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Søk i Nord-Norge reiselivsregisteret"
    )
    parser.add_argument("--db",           default=DEFAULT_DB,
                        help=f"Database path (default: {DEFAULT_DB})")
    parser.add_argument("--search",       help="Full-text search term")
    parser.add_argument("--county",       help="Filter by county name")
    parser.add_argument("--municipality", help="Filter by municipality name")
    parser.add_argument("--nace",         help="Filter by NACE code prefix (e.g. 79)")
    parser.add_argument("--status",       default="active",
                        choices=["active", "dissolved", "bankrupt", "winding_down", "all"],
                        help="Company status filter (default: active)")
    parser.add_argument("--no-website",   action="store_true",
                        help="Only companies without a website")
    parser.add_argument("--has-website",  action="store_true",
                        help="Only companies with a known website")
    parser.add_argument("--svalbard",     action="store_true",
                        help="Svalbard companies only")
    parser.add_argument("--summary",      action="store_true",
                        help="Print database statistics and exit")
    parser.add_argument("--export",       metavar="FILE",
                        help="Export results to CSV or JSON file")
    parser.add_argument("--to-scan-csv",  metavar="FILE",
                        help="Export results as scanner-ready CSV (FinnmarkTravel.csv format)")
    parser.add_argument("--limit",        type=int, default=500,
                        help="Max rows to return (default: 500)")
    args = parser.parse_args()

    conn = open_db(args.db)

    if args.summary:
        print_summary(conn)
        conn.close()
        return

    # Build and run query
    status_filter = None if args.status == "all" else args.status
    any_filter = any([
        args.search, args.county, args.municipality, args.nace,
        args.no_website, args.has_website, args.svalbard
    ])

    if any_filter:
        sql, params = build_query(
            search=args.search,
            county=args.county,
            municipality=args.municipality,
            nace=args.nace,
            status=status_filter,
            no_website=args.no_website,
            has_website=args.has_website,
            svalbard=args.svalbard,
            limit=args.limit,
        )
        rows = [row_to_dict(r) for r in conn.execute(sql, params)]
        total = count_query(sql, params, conn)
        print_results(rows, total)

        if args.export:
            if args.export.endswith(".json"):
                export_json(rows, args.export)
            else:
                export_csv(rows, args.export)

        if args.to_scan_csv:
            export_for_scanner(rows, args.to_scan_csv)

    else:
        # No filters: enter interactive mode
        print_summary(conn)
        interactive_mode(conn)

    conn.close()


if __name__ == "__main__":
    main()
