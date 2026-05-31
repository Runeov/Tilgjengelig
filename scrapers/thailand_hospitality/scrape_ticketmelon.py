"""Scrape Ticketmelon for live SHOWS in Thailand (concerts, Muay Thai, cabaret).

Ticketmelon is the strongest pure "show" source — it lists ticketed events with
their venue, which OSM tags only sparsely. We map each event -> a venue row with
venue_type="show".

Strategy (chosen because the site blocks naive fetches and renders via a JS app):
prefer the embedded JSON the page ships rather than scraping rendered HTML.
Next.js apps expose it as <script id="__NEXT_DATA__">; some pages also include
schema.org <script type="application/ld+json"> Event objects. Both are far more
stable than CSS selectors. We try, in order:
  1) __NEXT_DATA__  -> props.pageProps (events list)
  2) ld+json Event objects
  3) (fallback) anchor scan for /event/<id> links

Output: data/ticketmelon_<slug>.csv in the shared scrape_osm schema.

Usage:
  python scrape_ticketmelon.py --slug thailand
  python scrape_ticketmelon.py --slug bangkok --query bangkok
  python scrape_ticketmelon.py --selftest          # offline: verify row mapping

⚠️ NETWORK + SELECTORS PENDING VALIDATION: the JSON key paths below are the
documented best-effort shape; confirm/adjust them on the first networked run
(print --dump-json to see the real payload), then remove this notice.

Requires: requests, beautifulsoup4 (already in ../../requirements.txt)
"""

import argparse
import csv
import json
import os
import sys
import time

from scrape_osm import CSV_FIELDS, DATA_DIR

BASE = "https://www.ticketmelon.com"
DISCOVERY = BASE + "/discovery"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
DEFAULT_DELAY = 10  # be polite; raise if throttled


def fetch_html(url: str, delay: float = DEFAULT_DELAY) -> str:
    import requests
    time.sleep(delay)
    r = requests.get(url, headers={"User-Agent": UA,
                                   "Accept-Language": "en"}, timeout=30)
    r.raise_for_status()
    return r.text


def extract_events(html: str) -> list[dict]:
    """Pull a list of raw event dicts from a page's embedded JSON.

    Returns whatever event-like objects we can find; map_row normalises them.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    events: list[dict] = []

    # 1) __NEXT_DATA__
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag and tag.string:
        try:
            data = json.loads(tag.string)
            page = (data.get("props", {}) or {}).get("pageProps", {}) or {}
            # Common shapes: pageProps.events / .items / .results / .discovery.events
            for key in ("events", "items", "results", "list"):
                v = page.get(key)
                if isinstance(v, list):
                    events.extend([e for e in v if isinstance(e, dict)])
            disc = page.get("discovery") or page.get("data") or {}
            if isinstance(disc, dict):
                for key in ("events", "items", "results"):
                    v = disc.get(key)
                    if isinstance(v, list):
                        events.extend([e for e in v if isinstance(e, dict)])
        except ValueError:
            pass

    # 2) schema.org Event objects
    for s in soup.find_all("script", type="application/ld+json"):
        if not s.string:
            continue
        try:
            obj = json.loads(s.string)
        except ValueError:
            continue
        for node in obj if isinstance(obj, list) else [obj]:
            if isinstance(node, dict) and "Event" in str(node.get("@type", "")):
                events.append(node)

    return events


def _loc_field(ev: dict, *path):
    cur = ev
    for p in path:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(p)
    return cur or ""


def map_row(ev: dict) -> dict:
    """Normalise one raw event dict into the shared CSV schema (venue_type=show)."""
    # Accept both __NEXT_DATA__-style and schema.org Event shapes.
    name = ev.get("name") or ev.get("title") or ev.get("eventName") or ""
    # venue / location
    venue = (ev.get("venue") or ev.get("venueName")
             or _loc_field(ev, "location", "name")
             or _loc_field(ev, "location", "@type") and ev.get("location", {}).get("name", "")
             or "")
    addr = (_loc_field(ev, "location", "address", "streetAddress")
            or _loc_field(ev, "location", "address")
            or ev.get("address") or ev.get("city") or "")
    if isinstance(addr, dict):
        addr = addr.get("streetAddress") or addr.get("addressLocality") or ""
    url = ev.get("url") or ev.get("permalink") or ev.get("slug") or ""
    if url and url.startswith("/"):
        url = BASE + url
    elif url and not url.startswith("http"):
        url = f"{BASE}/event/{url}"

    row = {k: "" for k in CSV_FIELDS}
    row.update({
        "name": (name or venue).strip(),
        "venue_type": "show",
        "category": "event",
        "subcategory": ev.get("category") or ev.get("eventType") or "show",
        "website": url,
        "address_full": addr.strip() if isinstance(addr, str) else "",
        "operator": venue.strip() if isinstance(venue, str) else "",
    })
    # geo if present
    geo = ev.get("geo") or _loc_field(ev, "location", "geo") or {}
    if isinstance(geo, dict):
        row["lat"] = geo.get("latitude") or geo.get("lat") or ""
        row["lng"] = geo.get("longitude") or geo.get("lng") or geo.get("lon") or ""
    return row


def _dedupe(rows: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        key = (r["name"].strip().lower(), str(r.get("website", "")).lower())
        if not r["name"] or key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _write(rows: list[dict], slug: str) -> str:
    out_path = os.path.join(DATA_DIR, f"ticketmelon_{slug.lower()}.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CSV_FIELDS})
    return out_path


def _selftest() -> int:
    """Verify map_row on synthetic __NEXT_DATA__ and ld+json shapes (offline)."""
    next_data = {
        "name": "Muay Thai Live", "venue": "Asiatique Theatre",
        "slug": "muay-thai-live", "category": "Muay Thai",
        "geo": {"latitude": 13.7, "longitude": 100.5},
    }
    ld = {
        "@type": "Event", "name": "Cabaret Night",
        "url": "/event/cabaret-night",
        "location": {"name": "Calypso", "address": {"streetAddress": "Asiatique"}},
    }
    r1, r2 = map_row(next_data), map_row(ld)
    checks = [
        (r1["name"] == "Muay Thai Live", "next: name"),
        (r1["venue_type"] == "show", "next: venue_type"),
        (r1["website"].endswith("/event/muay-thai-live"), "next: url from slug"),
        (r1["lat"] == 13.7, "next: geo lat"),
        (r2["name"] == "Cabaret Night", "ld: name"),
        (r2["website"] == BASE + "/event/cabaret-night", "ld: absolute url"),
        (r2["address_full"] == "Asiatique", "ld: nested address"),
        (r2["operator"] == "Calypso", "ld: venue->operator"),
    ]
    ok = True
    for passed, label in checks:
        if not passed:
            ok = False
        print(f"  [{'ok ' if passed else 'BAD'}] {label}")
    print("[selftest]", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--slug", help="Output slug -> data/ticketmelon_<slug>.csv")
    p.add_argument("--query", help="Discovery search/location query (e.g. 'bangkok')")
    p.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    p.add_argument("--dump-json", action="store_true",
                   help="Print the raw extracted events JSON (for confirming key paths)")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args()

    if args.selftest:
        return _selftest()
    if not args.slug:
        p.error("--slug is required (or use --selftest)")

    url = DISCOVERY + (f"?q={args.query}" if args.query else "")
    html = fetch_html(url, args.delay)
    events = extract_events(html)
    print(f"[ticketmelon] extracted {len(events)} raw events from {url}")
    if args.dump_json:
        print(json.dumps(events[:5], indent=2, ensure_ascii=False))
    rows = _dedupe([map_row(e) for e in events])
    out = _write(rows, args.slug)
    print(f"[ticketmelon] wrote {len(rows)} show rows -> {out}")
    if not rows:
        print("[ticketmelon] 0 rows — confirm the JSON key paths with --dump-json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
