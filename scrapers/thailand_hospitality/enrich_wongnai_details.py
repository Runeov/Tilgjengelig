"""Fetch Wongnai detail pages to extract phone + hours + cuisine + price range.

Input:  data/wongnai_<slug>.csv produced by scrape_wongnai.py
Output: data/wongnai_<slug>_detailed.csv with original cols + new fields:
  telephone, address_street, opening_hours_summary, rating, review_count,
  price_range, serves_cuisine, image_url

Source: <script type="application/ld+json"> with @type='Restaurant' or
'FoodEstablishment' on each shop's detail page.

Usage:
  python enrich_wongnai_details.py udonthani
  python enrich_wongnai_details.py udonthani --limit 20  # sanity-test
  python enrich_wongnai_details.py udonthani --resume    # continue after a crash
  python enrich_wongnai_details.py udonthani --food-only # skip non-food rows
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0 Safari/537.36"
)
# Wongnai 403s aggressively. 2.5s gets banned fast in bulk; use --delay 15+
# for sustained runs.
CRAWL_DELAY = 2.5
RETRY_BACKOFF = 30.0

DETAIL_FIELDS = [
    "telephone", "address_street", "opening_hours_summary",
    "rating", "review_count", "price_range", "serves_cuisine",
    "image_url", "detail_fetch_status",
]


def fetch_html(url: str, allow_retry: bool = True) -> Optional[str]:
    r = requests.get(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "th-TH,th;q=0.9,en;q=0.8",
            "Referer": "https://www.wongnai.com/",
        },
        timeout=20,
        allow_redirects=True,
    )
    if r.status_code == 403 and allow_retry:
        print(f"  [retry] 403, sleeping {RETRY_BACKOFF}s then retrying once...")
        time.sleep(RETRY_BACKOFF)
        return fetch_html(url, allow_retry=False)
    if r.status_code != 200:
        return None
    return r.text


def summarize_hours(hours_list) -> str:
    """Compact a list of OpeningHoursSpecification objects into a short string."""
    if not hours_list:
        return ""
    if isinstance(hours_list, dict):
        hours_list = [hours_list]
    parts = []
    for h in hours_list:
        days = h.get("dayOfWeek") or []
        if isinstance(days, str):
            days = [days]
        opens = h.get("opens") or ""
        closes = h.get("closes") or ""
        days_str = ",".join(d[:3] for d in days)
        parts.append(f"{days_str} {opens}-{closes}".strip())
    return " | ".join(parts)[:200]


def extract_fields(html_text: str) -> dict:
    out = {f: "" for f in DETAIL_FIELDS}
    if not html_text:
        out["detail_fetch_status"] = "no_html"
        return out
    soup = BeautifulSoup(html_text, "lxml")
    found = False
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            d = json.loads(s.string or "")
        except Exception:
            continue
        t = d.get("@type")
        if t not in ("Restaurant", "FoodEstablishment", "BarOrPub", "LocalBusiness"):
            continue
        found = True
        out["telephone"] = (d.get("telephone") or "").strip()
        addr = d.get("address") or {}
        if isinstance(addr, dict):
            out["address_street"] = (addr.get("streetAddress") or "").strip()
        elif isinstance(addr, str):
            out["address_street"] = addr.strip()
        out["opening_hours_summary"] = summarize_hours(d.get("openingHoursSpecification"))
        rating = d.get("aggregateRating") or {}
        if isinstance(rating, dict):
            out["rating"] = str(rating.get("ratingValue") or "")
            out["review_count"] = str(rating.get("reviewCount") or rating.get("ratingCount") or "")
        out["price_range"] = (d.get("priceRange") or "").strip()
        cuisine = d.get("servesCuisine") or ""
        if isinstance(cuisine, list):
            cuisine = ", ".join(cuisine)
        out["serves_cuisine"] = (cuisine or "").strip()
        out["image_url"] = (d.get("image") or "").strip() if isinstance(d.get("image"), str) else ""
        out["detail_fetch_status"] = "ok"
        break
    if not found:
        out["detail_fetch_status"] = "no_jsonld"
    return out


def load_already_done(out_path: str) -> set:
    """Return source publicIds that already have a successful enrichment."""
    done: set = set()
    if not os.path.exists(out_path):
        return done
    with open(out_path, "r", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("publicId") and r.get("detail_fetch_status") in ("ok", "no_jsonld"):
                done.add(r["publicId"])
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slug", help="Region slug matching the input CSV (e.g. 'udonthani')")
    parser.add_argument("--limit", type=int, default=None, help="Only enrich first N rows")
    parser.add_argument("--food-only", action="store_true",
                        help="Skip rows where is_likely_food=0 (saves time on temples/parks)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip rows that already have detail_fetch_status set in the output file")
    parser.add_argument("--delay", type=float, default=CRAWL_DELAY,
                        help=f"Seconds between detail-page fetches (default {CRAWL_DELAY}). "
                             "Use 15+ for sustained runs to avoid Wongnai ban.")
    args = parser.parse_args()

    in_path = os.path.join(DATA_DIR, f"wongnai_{args.slug}.csv")
    out_path = os.path.join(DATA_DIR, f"wongnai_{args.slug}_detailed.csv")
    if not os.path.exists(in_path):
        raise SystemExit(f"Input not found: {in_path}. Run scrape_wongnai.py {args.slug} first.")

    with open(in_path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"[enrich] input: {len(rows):,} rows from {in_path}")

    if args.food_only:
        before = len(rows)
        rows = [r for r in rows if r.get("is_likely_food") == "1"]
        print(f"[enrich] --food-only: kept {len(rows)}/{before} rows")
    if args.limit:
        rows = rows[: args.limit]

    in_fields = list(rows[0].keys()) if rows else []
    out_fields = in_fields + [f for f in DETAIL_FIELDS if f not in in_fields]

    already_done = load_already_done(out_path) if args.resume else set()
    if already_done:
        print(f"[enrich] resume: {len(already_done)} rows already enriched")

    file_exists = os.path.exists(out_path)
    mode = "a" if (args.resume and file_exists) else "w"
    out_f = open(out_path, mode, encoding="utf-8", newline="")
    writer = csv.DictWriter(out_f, fieldnames=out_fields)
    if mode == "w":
        writer.writeheader()
        out_f.flush()

    to_fetch = [r for r in rows if r.get("publicId") not in already_done]
    print(f"[enrich] {len(to_fetch)} rows to enrich. delay={args.delay}s "
          f"-> est runtime ~{len(to_fetch) * (args.delay + 0.5) / 60:.1f} min")

    hits = misses = errors = 0
    try:
        for i, row in enumerate(to_fetch, 1):
            url = row.get("detail_url") or ""
            if not url:
                row.update({f: "" for f in DETAIL_FIELDS})
                row["detail_fetch_status"] = "no_url"
                writer.writerow({k: row.get(k, "") for k in out_fields})
                out_f.flush()
                continue
            if i > 1:
                time.sleep(args.delay)
            try:
                html_text = fetch_html(url)
            except Exception as e:
                row.update({f: "" for f in DETAIL_FIELDS})
                row["detail_fetch_status"] = f"err:{type(e).__name__}"
                writer.writerow({k: row.get(k, "") for k in out_fields})
                out_f.flush()
                errors += 1
                print(f"  [{i:>4}/{len(to_fetch)}] ERROR {row.get('displayName','')[:30]}: {e}")
                continue
            fields = extract_fields(html_text or "")
            row.update(fields)
            writer.writerow({k: row.get(k, "") for k in out_fields})
            out_f.flush()
            status = fields["detail_fetch_status"]
            phone = fields["telephone"] or "-"
            if status == "ok":
                hits += 1
            elif status == "no_jsonld":
                misses += 1
            else:
                errors += 1
            if i % 10 == 0 or i == len(to_fetch):
                print(f"  [{i:>4}/{len(to_fetch)}] {(row.get('displayName','') or '')[:25]:<25} "
                      f"| {status:<10} phone={phone}")
    finally:
        out_f.close()

    print(f"\n[enrich] done: hits={hits} misses={misses} errors={errors}")
    print(f"[enrich] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
