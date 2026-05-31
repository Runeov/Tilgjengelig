"""Scrape Wongnai's per-region business directory via their private JSON API.

Endpoint: GET https://www.wongnai.com/_api/regions/{slug}/businesses.json
                ?page.number=N&page.size=20

Slugs are lowercase no-hyphen Thai-city names (e.g. 'udonthani', 'bangkok',
'chiangmai'). The full slug map is in wongnai_regions.json next to this script.

Per-entity fields captured from the bulk list:
  id, publicId, gid, displayName, name (thai/en), lat, lng, zipcode,
  categories (full list as '|'-joined), primary_category, is_likely_food,
  default_photo_url, detail_url

Detail-page fetch (phone/hours/price-range/cuisine/etc.) is a separate step;
see enrich_wongnai_details.py.

Usage:
  python scrape_wongnai.py udonthani
  python scrape_wongnai.py bangkok --limit 200            # sanity-test
  python scrape_wongnai.py udonthani --food-only          # drop temples/parks
  python scrape_wongnai.py --list-regions                 # show all slugs
"""

import argparse
import csv
import json
import os
import sys
import time
from typing import Optional

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
REGIONS_PATH = os.path.join(SCRIPT_DIR, "wongnai_regions.json")
os.makedirs(DATA_DIR, exist_ok=True)

API_BASE = "https://www.wongnai.com/_api"
DETAIL_BASE = "https://www.wongnai.com/restaurants"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0 Safari/537.36"
)
PAGE_SIZE = 20
# Wongnai 403s aggressively. 2.5s got us banned after ~80 reqs across multiple
# cities; 15s is what we settled on for safe sustained runs. Override per-run
# via --delay.
CRAWL_DELAY = 2.5
# On HTTP 403, wait this long then retry once before bailing.
RETRY_BACKOFF = 30.0

# Category-name keywords that mark a row as food/drink. Wongnai's API mixes
# in temples (วัด), parks (อุทยาน), historical sites (ประวัติศาสตร์), shops, etc.
FOOD_KEYWORDS = (
    "อาหาร", "ร้านอาหาร", "คาเฟ่", "กาแฟ", "ชา", "เครื่องดื่ม", "น้ำผลไม้",
    "เบเกอรี", "เค้ก", "ก๋วยเตี๋ยว", "ของหวาน", "ปิ้งย่าง", "ฟาสต์ฟู้ด",
    "ไอศกรีม", "พิซซ่า", "ผับ", "บาร์", "ร้านเหล้า", "ส้มตำ", "ข้าว",
    "ซูชิ", "ราเมง", "เบเกอรี", "เครป", "บุฟเฟต์", "buffet", "ramen",
    "sushi", "pizza", "burger", "bar", "pub", "cafe", "coffee", "restaurant",
    "bakery", "dessert", "noodle", "thai food", "เบอร์เกอร์",
)


def load_regions() -> dict:
    """Load wongnai_regions.json. Returns {slug: {name, id, ...}} mapping."""
    if not os.path.exists(REGIONS_PATH):
        return {}
    with open(REGIONS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    out: dict = {}
    for c in data.get("cities", []):
        slug = c.get("url") or ""
        if slug:
            out[slug] = c
    return out


def resolve_slug(arg: str, regions: dict) -> str:
    """Accept either a slug or a city name (Thai or English)."""
    arg_lower = arg.lower().strip()
    if arg_lower in regions:
        return arg_lower
    # Match by name (English / Thai)
    for slug, c in regions.items():
        names = [
            (c.get("name") or "").lower(),
            (c.get("shortName") or "").lower(),
            ((c.get("nameOnly") or {}).get("english") or "").lower(),
            ((c.get("nameOnly") or {}).get("thai") or "").lower(),
        ]
        if any(arg_lower == n for n in names if n):
            return slug
    # Fall-through: treat the arg as a raw API slug. Useful for slugs like
    # "1009-pattaya" that don't match a clean entry in wongnai_regions.json.
    print(f"[wongnai] no regions.json match for {arg!r}; using as raw slug")
    return arg


def is_food_drink(entity: dict) -> bool:
    """Coarse classifier — true if any category name contains a food keyword."""
    for cat in entity.get("categories", []) or []:
        name = (cat.get("name") or "").lower()
        if any(kw.lower() in name for kw in FOOD_KEYWORDS):
            return True
    return False


def build_detail_url(public_id: str, display_name: str) -> str:
    """Construct the canonical /restaurants/<publicId>-<slug> URL.

    Wongnai accepts both `/restaurants/<publicId>` (redirects to canonical)
    and `/restaurants/<publicId>-<slug>` directly. We use the publicId-only
    form for stability across name changes.
    """
    if not public_id:
        return ""
    return f"{DETAIL_BASE}/{public_id}"


def extract_row(e: dict) -> dict:
    """Flatten a Wongnai entity into our CSV row schema."""
    categories = e.get("categories") or []
    primary_cat = (categories[0].get("name") if categories else "") or ""
    cat_names = "|".join((c.get("name") or "") for c in categories)
    photo = e.get("defaultPhoto") or {}
    name_only = e.get("nameOnly") or {}
    return {
        "id": e.get("id"),
        "publicId": e.get("publicId") or "",
        "gid": e.get("gid") or "",
        "displayName": e.get("displayName") or e.get("name") or "",
        "name_thai": name_only.get("thai") or "",
        "name_english": name_only.get("english") or "",
        "lat": e.get("lat"),
        "lng": e.get("lng"),
        "zipcode": e.get("zipcode") or "",
        "categories": cat_names,
        "primary_category": primary_cat,
        "is_likely_food": "1" if is_food_drink(e) else "0",
        "default_photo_url": photo.get("contentUrl") or "",
        "detail_url": build_detail_url(e.get("publicId") or "", e.get("displayName") or ""),
    }


CSV_FIELDS = [
    "id", "publicId", "gid", "displayName", "name_thai", "name_english",
    "lat", "lng", "zipcode", "categories", "primary_category",
    "is_likely_food", "default_photo_url", "detail_url",
]


def fetch_page(slug: str, page: int, allow_retry: bool = True) -> dict:
    url = f"{API_BASE}/regions/{slug}/businesses.json"
    headers = {
        "User-Agent": UA,
        "Accept": "application/json",
        "Referer": "https://www.wongnai.com/",
    }
    params = {"page.number": page, "page.size": PAGE_SIZE}
    r = requests.get(url, params=params, headers=headers, timeout=20)
    if r.status_code == 403 and allow_retry:
        print(f"  [retry] 403 on page {page}, sleeping {RETRY_BACKOFF}s then retrying once...")
        time.sleep(RETRY_BACKOFF)
        return fetch_page(slug, page, allow_retry=False)
    r.raise_for_status()
    return r.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("region", nargs="?", help="Region slug or city name (e.g. 'udonthani' or 'Bangkok')")
    parser.add_argument("--out-slug", help="Clean slug for the output filename (wongnai_<slug>.csv). "
                                           "Use when 'region' is a name or URL-encoded slug, so the "
                                           "output filename stays clean and matches the merge step.")
    parser.add_argument("--limit", type=int, default=None, help="Only fetch N entities (sanity-test)")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Cap at N pages (PAGE_SIZE=20). Use to control big cities (Bangkok has 40K+ pages).")
    parser.add_argument("--food-only", action="store_true",
                        help="Filter out non-food/drink entries (temples, parks, etc.)")
    parser.add_argument("--list-regions", action="store_true",
                        help="Print all known Wongnai region slugs, then exit.")
    parser.add_argument("--resume", action="store_true",
                        help="Continue an interrupted run. Reads the existing output CSV, "
                             "counts rows, resumes from the next page (page = (rows / PAGE_SIZE) + 1).")
    parser.add_argument("--delay", type=float, default=CRAWL_DELAY,
                        help=f"Seconds between page fetches (default {CRAWL_DELAY}). "
                             "Use 15+ for retry runs after a 403/IP ban.")
    args = parser.parse_args()

    regions = load_regions()
    if args.list_regions:
        print(f"{'slug':<35}  {'name':<35}  type")
        print("-" * 85)
        for slug, c in sorted(regions.items()):
            print(f"  {slug[:33]:<33}  {(c.get('name') or '')[:33]:<33}  {(c.get('type') or {}).get('name', '?')}")
        return 0

    if not args.region:
        parser.error("region argument required (or use --list-regions)")

    slug = resolve_slug(args.region, regions)
    print(f"[wongnai] resolved {args.region!r} -> slug {slug!r}")

    # Probe first page to get total count
    first = fetch_page(slug, 1)
    total = first["page"]["totalNumberOfEntities"]
    total_pages = first["page"]["totalNumberOfPages"]
    print(f"[wongnai] total entities: {total:,}  total pages: {total_pages}")
    if args.limit:
        cap_pages = min(total_pages, -(-args.limit // PAGE_SIZE))  # ceil div
        print(f"[wongnai] --limit {args.limit}: capping at {cap_pages} pages")
    elif args.max_pages:
        cap_pages = min(total_pages, args.max_pages)
        print(f"[wongnai] --max-pages {args.max_pages}: capping at {cap_pages} pages "
              f"(~{cap_pages * PAGE_SIZE} entities)")
    else:
        cap_pages = total_pages

    est_secs = cap_pages * (CRAWL_DELAY + 1)
    print(f"[wongnai] est runtime: ~{est_secs:.0f}s ({est_secs/60:.1f} min)")

    out_slug = (args.out_slug or slug).strip()
    out_path = os.path.join(DATA_DIR, f"wongnai_{out_slug}.csv")
    print(f"[wongnai] output: {out_path}")

    # Resume: count existing rows, compute starting page
    start_page = 1
    written_before = 0
    if args.resume and os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8", newline="") as f:
            written_before = sum(1 for _ in f) - 1  # subtract header
        start_page = (written_before // PAGE_SIZE) + 1
        print(f"[wongnai] resume: {written_before} rows in file, restarting at page {start_page}")
        mode = "a"
    else:
        mode = "w"

    out_f = open(out_path, mode, encoding="utf-8", newline="")
    writer = csv.DictWriter(out_f, fieldnames=CSV_FIELDS)
    if mode == "w":
        writer.writeheader()
        out_f.flush()

    written = 0
    skipped_non_food = 0
    try:
        for page in range(start_page, cap_pages + 1):
            if page == 1:
                d = first
            else:
                time.sleep(args.delay)
                d = fetch_page(slug, page)
            ents = d["page"]["entities"]
            for e in ents:
                row = extract_row(e)
                if args.food_only and row["is_likely_food"] != "1":
                    skipped_non_food += 1
                    continue
                writer.writerow(row)
                written += 1
                if args.limit and written >= args.limit:
                    break
            out_f.flush()
            print(f"  page {page}/{cap_pages}  ents={len(ents)}  written this run={written}  total={written_before + written}")
            if args.limit and written >= args.limit:
                break
    finally:
        out_f.close()

    print(f"\n[wongnai] done: wrote {written} entities -> {out_path}")
    if args.food_only:
        print(f"[wongnai] skipped {skipped_non_food} non-food entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
