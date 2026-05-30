"""Scan the REST of Thailand: every province not yet covered by the hospitality
pipeline, with full bar + show (nightlife/cabaret/Muay-Thai) capture via OSM.

This complements run_all_cities.py (which targets the original tourism hot-spots).
It reads wongnai_regions.json, lists every CITY-type Thai province, skips the ones
that already have data, and runs the 3-step pipeline for the rest:

  1. scrape_wongnai.py "<English name>" --out-slug <slug>   (restaurants/cafes/bars)
  2. scrape_osm.py <slug> --place "<English name>, Thailand" (lodging/attractions/
                                                              BARS + SHOWS via OSM)
  3. merge_hospitality.py <slug>                            (dedupe + lead-score)

OSM bboxes are resolved on the fly through Nominatim (--place), so no province
needs hand-curated coordinates. Wongnai is passed the English name and resolves
the real (often URL-encoded) API slug itself, while --out-slug keeps filenames clean.

Resume-safe: a province is skipped if hospitality_<slug>.csv already exists.
Conservative defaults respect Wongnai's ~80-req/2-min IP rate limit.

Usage:
  python run_remaining_provinces.py --list              # show remaining provinces, exit
  python run_remaining_provinces.py                     # run them all (long!)
  python run_remaining_provinces.py --limit 8           # only the next 8 (one safe batch)
  python run_remaining_provinces.py --skip-wongnai      # OSM bars+shows only (faster, no 403 risk)
  python run_remaining_provinces.py --max-pages 50 --wongnai-delay 15

After a run, fold results into the country files:
  python aggregate_country.py
  python finalize_country.py
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
REGIONS_PATH = os.path.join(SCRIPT_DIR, "wongnai_regions.json")

# Hosts that MUST be reachable for a live scrape. A new Claude Code web session
# needs a network policy that allowlists all three (see SCAN_REST_OF_THAILAND.md).
REQUIRED_HOSTS = {
    "Overpass (OSM bars+shows)": "https://overpass-api.de/api/status",
    "Nominatim (province bboxes)": "https://nominatim.openstreetmap.org/status",
    "Wongnai (restaurants+bars)": "https://www.wongnai.com/_api/regions/udonthani/businesses.json?page.number=1&page.size=1",
}

# Provinces whose preferred Wongnai slug / output name differ from a naive
# transliteration of the English name. Keep this small and explicit.
SLUG_OVERRIDES = {
    "Nakhon Ratchasima": "korat",       # Wongnai uses 'korat'
    "Phang-nga": "phangnga",
    "Buri Ram": "burinam",              # matches existing hospitality_burinam.csv
    "Surat Thani": "surat-thani",       # matches existing hospitality_surat-thani.csv
    "Phetchaburi": "petchaburi",        # matches existing hospitality_petchaburi.csv
}

# Non-Thai entries in regions.json we never want to scan.
EXCLUDE_NAMES = {"Singapore"}


def slugify(name: str) -> str:
    """ASCII clean slug for output filenames: 'Nakhon Phanom' -> 'nakhonphanom'."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def english_name(c: dict) -> str:
    return ((c.get("nameOnly") or {}).get("english")
            or c.get("shortName") or c.get("name") or "").strip()


def load_provinces() -> list[dict]:
    """Return [{name, slug, region_slug}] for every CITY-type Thai province."""
    with open(REGIONS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for c in data.get("cities", []):
        if (c.get("type") or {}).get("name") != "CITY":
            continue
        name = english_name(c)
        if not name or name in EXCLUDE_NAMES:
            continue
        slug = SLUG_OVERRIDES.get(name) or slugify(name)
        out.append({"name": name, "slug": slug, "region_slug": c.get("url") or ""})
    # De-dup by slug, keep first
    seen, uniq = set(), []
    for p in out:
        if p["slug"] in seen:
            continue
        seen.add(p["slug"])
        uniq.append(p)
    return uniq


def already_done(slug: str) -> bool:
    return os.path.exists(os.path.join(DATA_DIR, f"hospitality_{slug}.csv"))


def preflight(require: bool) -> bool:
    """Check the required hosts are reachable. Returns True if all OK.

    `require=True` aborts the run on failure; otherwise it's just a warning.
    """
    try:
        import requests
    except ImportError:
        print("[preflight] 'requests' not installed: pip install -r requirements.txt")
        return not require
    print("[preflight] checking data-source reachability...")
    ua = {"User-Agent": "Mozilla/5.0 (TH-hospitality-research)"}
    all_ok = True
    for label, url in REQUIRED_HOSTS.items():
        try:
            r = requests.get(url, headers=ua, timeout=15)
            ok = r.status_code < 400
            print(f"    {'OK ' if ok else 'BLOCKED'}  {label}  (HTTP {r.status_code})")
        except Exception as e:
            ok = False
            print(f"    BLOCKED  {label}  ({type(e).__name__}: {str(e)[:60]})")
        all_ok = all_ok and ok
    if not all_ok:
        print("[preflight] one or more hosts are blocked. This session's network policy "
              "must allowlist overpass-api.de, nominatim.openstreetmap.org and "
              "www.wongnai.com. See SCAN_REST_OF_THAILAND.md.")
    return all_ok


def run(cmd: list[str], label: str) -> bool:
    print(f"\n>>> {label}\n    cmd: {' '.join(cmd)}")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                          encoding="utf-8", errors="replace")
    elapsed = time.time() - t0
    if proc.returncode == 0:
        for line in (proc.stdout or "").strip().splitlines()[-3:]:
            print(f"    {line}")
        print(f"    [{label}] DONE in {elapsed:.0f}s")
        return True
    print(f"    [{label}] FAILED rc={proc.returncode} ({elapsed:.0f}s)")
    for line in (proc.stderr or "").strip().splitlines()[-5:]:
        print(f"    ! {line}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="Print remaining provinces and exit")
    parser.add_argument("--check", action="store_true",
                        help="Only run the network preflight (check data-source reachability) and exit")
    parser.add_argument("--no-preflight", action="store_true",
                        help="Skip the reachability check before scraping")
    parser.add_argument("--limit", type=int, default=None, help="Only process the next N remaining provinces")
    parser.add_argument("--max-pages", type=int, default=50,
                        help="Max Wongnai pages per province (default 50 = ~1K shops)")
    parser.add_argument("--wongnai-delay", type=float, default=15.0,
                        help="Seconds between Wongnai page fetches (default 15; safe sustained rate)")
    parser.add_argument("--inter-city-delay", type=int, default=60,
                        help="Cool-off seconds between provinces (default 60)")
    parser.add_argument("--skip-wongnai", action="store_true", help="Skip Wongnai (OSM bars+shows only)")
    parser.add_argument("--skip-osm", action="store_true", help="Skip OSM (no bars/shows from OSM)")
    parser.add_argument("--skip-merge", action="store_true")
    parser.add_argument("--include-done", action="store_true",
                        help="Don't skip provinces that already have hospitality_<slug>.csv")
    args = parser.parse_args()

    if args.check:
        return 0 if preflight(require=True) else 2

    provinces = load_provinces()
    remaining = [p for p in provinces if args.include_done or not already_done(p["slug"])]
    if args.limit:
        remaining = remaining[:args.limit]

    if args.list:
        print(f"{len(provinces)} CITY provinces total; {len(remaining)} to process:\n")
        for p in remaining:
            print(f"  {p['slug']:<22} {p['name']}")
        done = [p for p in provinces if already_done(p["slug"])]
        print(f"\n(already done: {len(done)})")
        return 0

    print(f"[remaining] {len(remaining)} provinces to scan")

    if not args.no_preflight and not preflight(require=True):
        print("[abort] data sources unreachable; nothing scraped. "
              "Use --no-preflight to override, or fix the network policy.")
        return 2

    py = sys.executable
    failures = []
    for i, p in enumerate(remaining, 1):
        slug, name = p["slug"], p["name"]
        print(f"\n{'='*70}\n  [{i}/{len(remaining)}] {name}  (slug={slug})\n{'='*70}")

        if not args.skip_wongnai:
            ok = run([py, os.path.join(SCRIPT_DIR, "scrape_wongnai.py"),
                      name, "--out-slug", slug,
                      "--max-pages", str(args.max_pages),
                      "--delay", str(args.wongnai_delay)],
                     f"wongnai {slug}")
            if not ok:
                failures.append((slug, "wongnai"))

        if not args.skip_osm:
            ok = run([py, os.path.join(SCRIPT_DIR, "scrape_osm.py"),
                      slug, "--place", f"{name}, Thailand"],
                     f"osm {slug}")
            if not ok:
                failures.append((slug, "osm"))

        if not args.skip_merge:
            ok = run([py, os.path.join(SCRIPT_DIR, "merge_hospitality.py"), slug],
                     f"merge {slug}")
            if not ok:
                failures.append((slug, "merge"))

        if i < len(remaining):
            print(f"    cool-off {args.inter_city_delay}s before next province...")
            time.sleep(args.inter_city_delay)

    print(f"\n{'='*70}\n  DONE — processed {len(remaining)} provinces. Failures: {len(failures)}")
    for slug, step in failures:
        print(f"  - {slug}: {step}")
    print("\nNext: python aggregate_country.py && python finalize_country.py")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
