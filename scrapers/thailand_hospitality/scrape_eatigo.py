"""Scrape Eatigo for restaurants & bars in Thailand (reservation platform).

Eatigo adds dine-in restaurant + bar density (and a contactable subset, since
listings carry booking/area info) that complements Wongnai. Bars/pubs/buffets
appear with cuisine tags we map to venue_type.

Strategy: Eatigo is a React SPA that blocks naive fetches, so we prefer the
embedded JSON over rendered HTML. Next.js exposes <script id="__NEXT_DATA__">;
the region pages (e.g. /en/regions/28 = Bangkok) embed the restaurant list under
props.pageProps. We parse that; if absent, fall back to any JSON the page ships.

Output: data/eatigo_<slug>.csv in the shared scrape_osm schema.

Usage:
  python scrape_eatigo.py --slug bangkok --region 28
  python scrape_eatigo.py --selftest        # offline: verify row mapping

Region IDs (from eatigo.com/en/regions/<id>): 28=Bangkok. Discover others by
browsing the site's region switcher (note them here as you confirm them).

⚠️ NETWORK + KEY PATHS PENDING VALIDATION: confirm the props.pageProps shape on
the first networked run with --dump-json, then adjust map_row / list discovery.

Requires: requests, beautifulsoup4 (already in ../../requirements.txt)
"""

import argparse
import csv
import json
import os
import sys
import time

from scrape_osm import CSV_FIELDS, DATA_DIR

BASE = "https://eatigo.com"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
DEFAULT_DELAY = 8

# Map Eatigo cuisine/category text -> coarse venue_type. Bars/pubs/clubs -> bar;
# everything else dine-in stays restaurant (is_food).
BAR_HINTS = ("bar", "pub", "club", "lounge", "brewery", "beer", "cocktail", "wine")


def cuisine_to_venue_type(cuisine: str) -> str:
    c = (cuisine or "").lower()
    if any(h in c for h in BAR_HINTS):
        return "bar"
    return "restaurant"


def fetch_html(url: str, delay: float = DEFAULT_DELAY) -> str:
    import requests
    time.sleep(delay)
    r = requests.get(url, headers={"User-Agent": UA,
                                   "Accept-Language": "en"}, timeout=30)
    r.raise_for_status()
    return r.text


def extract_restaurants(html: str) -> list[dict]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag and tag.string:
        try:
            data = json.loads(tag.string)
            page = (data.get("props", {}) or {}).get("pageProps", {}) or {}
            for key in ("restaurants", "shops", "items", "results", "list", "data"):
                v = page.get(key)
                if isinstance(v, list):
                    out.extend([e for e in v if isinstance(e, dict)])
                elif isinstance(v, dict):
                    for k2 in ("restaurants", "items", "results"):
                        vv = v.get(k2)
                        if isinstance(vv, list):
                            out.extend([e for e in vv if isinstance(e, dict)])
        except ValueError:
            pass
    return out


def map_row(rest: dict) -> dict:
    name = rest.get("name") or rest.get("restaurantName") or rest.get("title") or ""
    cuisine = rest.get("cuisine") or rest.get("cuisineName") or ""
    if isinstance(cuisine, list):
        cuisine = ", ".join(str(c.get("name", c) if isinstance(c, dict) else c)
                            for c in cuisine)
    area = (rest.get("area") or rest.get("neighborhood")
            or rest.get("location") or rest.get("district") or "")
    if isinstance(area, dict):
        area = area.get("name") or ""
    slug = rest.get("slug") or rest.get("urlSlug") or rest.get("id") or ""
    url = f"{BASE}/en/restaurant/{slug}" if slug else (rest.get("url") or "")

    row = {k: "" for k in CSV_FIELDS}
    row.update({
        "name": str(name).strip(),
        "venue_type": cuisine_to_venue_type(str(cuisine)),
        "category": "restaurant",
        "subcategory": str(cuisine).split(",")[0].strip().lower(),
        "cuisine": str(cuisine).strip(),
        "address_full": str(area).strip(),
        "website": url,
        "stars": rest.get("rating") or rest.get("ratingScore") or "",
    })
    lat = rest.get("lat") or rest.get("latitude") or _nested(rest, "geo", "lat")
    lng = rest.get("lng") or rest.get("longitude") or _nested(rest, "geo", "lng")
    row["lat"] = lat or ""
    row["lng"] = lng or ""
    return row


def _nested(d: dict, *path):
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(p)
    return cur or ""


def _dedupe(rows: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        key = (r["name"].strip().lower(), r["address_full"].strip().lower())
        if not r["name"] or key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _write(rows: list[dict], slug: str) -> str:
    out_path = os.path.join(DATA_DIR, f"eatigo_{slug.lower()}.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CSV_FIELDS})
    return out_path


def _selftest() -> int:
    cases = [
        ({"name": "Brewski Rooftop", "cuisine": "Bar", "area": {"name": "Sukhumvit"},
          "slug": "brewski"}, "bar"),
        ({"restaurantName": "Sukiyaki House", "cuisine": ["Japanese", "Buffet"],
          "area": "Siam", "id": 42}, "restaurant"),
        ({"name": "Wine Connection", "cuisine": "Wine Bar", "slug": "wc"}, "bar"),
    ]
    ok = True
    for raw, want_vt in cases:
        r = map_row(raw)
        checks = [
            (r["venue_type"] == want_vt, f"{r['name']}: venue_type=={want_vt}"),
            (bool(r["name"]), f"{r['name']}: name present"),
            (r["website"].startswith(BASE), f"{r['name']}: url built"),
        ]
        for passed, label in checks:
            if not passed:
                ok = False
            print(f"  [{'ok ' if passed else 'BAD'}] {label}")
    print("[selftest]", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--slug", help="Output slug -> data/eatigo_<slug>.csv")
    p.add_argument("--region", help="Eatigo region id (28=Bangkok)")
    p.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    p.add_argument("--dump-json", action="store_true")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args()

    if args.selftest:
        return _selftest()
    if not args.slug or not args.region:
        p.error("--slug and --region are required (or use --selftest)")

    url = f"{BASE}/en/regions/{args.region}"
    html = fetch_html(url, args.delay)
    rests = extract_restaurants(html)
    print(f"[eatigo] extracted {len(rests)} raw restaurants from {url}")
    if args.dump_json:
        print(json.dumps(rests[:5], indent=2, ensure_ascii=False))
    rows = _dedupe([map_row(r) for r in rests])
    out = _write(rows, args.slug)
    print(f"[eatigo] wrote {len(rows)} rows -> {out}")
    if not rows:
        print("[eatigo] 0 rows — confirm props.pageProps shape with --dump-json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
