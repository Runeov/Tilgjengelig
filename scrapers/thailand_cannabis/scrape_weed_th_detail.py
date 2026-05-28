"""Fetch weed.th shop detail pages for a specific city to extract addresses.

Reads data/weed_th.csv (produced by scrape_weed_th.py), filters by city, and
fetches each detail page at the robots.txt-mandated 1-second crawl-delay.

What we extract from each detail page (JSON-LD Store schema):
  - name (also already in sitemap)
  - address (full street-level string — NOT in sitemap)
  - rating + review count
  - image

What we do NOT get (verified: not in weed.th detail pages):
  - phone, website, social links, email. For those, run enrich_google_places.py
    against this script's output.

Usage:
  python scrape_weed_th_detail.py "Udon Thani"
  python scrape_weed_th_detail.py "Udon Thani" --limit 5    # dry run
  python scrape_weed_th_detail.py --list-cities             # show available cities
"""

import argparse
import csv
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.thailand_cannabis.common import (  # noqa: E402
    DATA_DIR,
    DISPENSARY_FIELDS,
    Dispensary,
    dispensary_to_row,
    extract_jsonld,
    fetch,
    find_jsonld_by_type,
    write_csv,
)

INPUT_CSV = os.path.join(DATA_DIR, "weed_th.csv")
# robots.txt declares Crawl-delay: 1. We honor it.
CRAWL_DELAY = 1.0


def _to_float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _to_int(v):
    try:
        return int(float(v)) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def load_shops(city: str) -> list[dict]:
    with open(INPUT_CSV, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    # Normalize city comparison (case-insensitive, strip)
    target = city.strip().lower()
    return [r for r in rows if (r.get("city") or "").strip().lower() == target]


def parse_detail(base_row: dict, html: str) -> Dispensary:
    """Enrich a sitemap-derived row with detail-page JSON-LD data."""
    d = Dispensary(
        source="weed_th",
        source_id=base_row["source_id"],
        name=base_row["name"],
        city=base_row["city"],
        detail_url=base_row["detail_url"],
        lastmod=base_row.get("lastmod") or None,
    )
    blocks = extract_jsonld(html)
    store = find_jsonld_by_type(blocks, {"Store", "LocalBusiness", "Place"})
    if not store:
        return d
    # weed.th uses Store with a plain-string `address` (not PostalAddress object).
    address = store.get("address")
    if isinstance(address, dict):
        d.address = address.get("streetAddress") or str(address)
    elif isinstance(address, str):
        d.address = address
    # Name from JSON-LD is more authoritative than the URL slug
    if store.get("name"):
        d.name = store["name"]
    rating = store.get("aggregateRating") or {}
    d.rating = _to_float(rating.get("ratingValue"))
    d.review_count = _to_int(rating.get("reviewCount") or rating.get("ratingCount"))
    geo = store.get("geo") or {}
    d.latitude = _to_float(geo.get("latitude"))
    d.longitude = _to_float(geo.get("longitude"))
    if store.get("telephone"):
        d.phone = store["telephone"]
    return d


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("city", nargs="?", help="City to scrape (e.g. 'Udon Thani')")
    parser.add_argument("--limit", type=int, default=None, help="Only fetch N shops (dry run)")
    parser.add_argument("--list-cities", action="store_true", help="Show all cities and counts, then exit")
    args = parser.parse_args()

    if args.list_cities:
        with open(INPUT_CSV, "r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        counts = Counter(r.get("city", "") for r in rows)
        for city, n in counts.most_common():
            print(f"  {n:5d}  {city}")
        return 0

    if not args.city:
        parser.error("city argument required (or use --list-cities)")

    shops = load_shops(args.city)
    if not shops:
        print(f"[weed_th_detail] no shops found for city={args.city!r}. Try --list-cities.")
        return 1

    if args.limit:
        shops = shops[: args.limit]

    print(f"[weed_th_detail] city={args.city!r} shops={len(shops)} crawl_delay={CRAWL_DELAY}s")
    print(f"[weed_th_detail] estimated wall time: ~{len(shops) * (CRAWL_DELAY + 0.5):.0f}s")

    results: list[Dispensary] = []
    no_jsonld = 0
    errors = 0
    for i, row in enumerate(shops, 1):
        # No delay before the very first request.
        delay = 0.0 if i == 1 else CRAWL_DELAY
        try:
            html = fetch(row["detail_url"], delay=delay)
            d = parse_detail(row, html)
            results.append(d)
            addr_preview = (d.address[:50] + "...") if d.address and len(d.address) > 50 else (d.address or "(no address)")
            if not d.address:
                no_jsonld += 1
            print(f"  [{i}/{len(shops)}] {d.name[:35]:35s} | {addr_preview}")
        except Exception as e:
            errors += 1
            print(f"  [{i}/{len(shops)}] ERROR {row['name']}: {e}")

    # Output filename based on city
    safe_city = args.city.lower().replace(" ", "_")
    suffix = f"_limit{args.limit}" if args.limit else ""
    out_path = os.path.join(DATA_DIR, f"weed_th_{safe_city}{suffix}.csv")
    write_csv(out_path, [dispensary_to_row(d) for d in results], DISPENSARY_FIELDS)
    addresses_found = sum(1 for d in results if d.address)
    print(f"\n[weed_th_detail] wrote {len(results)} records -> {out_path}")
    print(f"[weed_th_detail] addresses extracted: {addresses_found}/{len(results)}; "
          f"missing JSON-LD: {no_jsonld}; fetch errors: {errors}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
