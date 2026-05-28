"""Enrich a scraped dispensary CSV with phone/website/hours from Google Places.

Uses the Google Places API (New) — places.googleapis.com/v1/places:searchText —
which returns contact fields in a single request via field masks (no separate
Place Details call needed, saving cost).

What gets added per row:
  google_place_id, google_phone, google_website, google_hours,
  google_rating, google_user_ratings, google_maps_uri,
  google_returned_address, google_match_confidence

Match confidence is a coarse signal (high/medium/low) based on whether the
returned formatted_address contains the input city. It is NOT a guarantee of
correctness — review low-confidence rows manually.

Setup (one-time):
  1. Google Cloud Console -> create project -> enable "Places API (New)"
  2. APIs & Services -> Credentials -> Create API Key
  3. Enable billing on the project (Places API requires it; $200/month free credit
     covers ~6,500 contact lookups before any out-of-pocket cost)
  4. Set env var:  $env:GOOGLE_MAPS_API_KEY = "AIza..."

Usage:
  python enrich_google_places.py data/weed_th_udon_thani.csv
  python enrich_google_places.py data/weed_th_udon_thani.csv --limit 5    # dry run
  python enrich_google_places.py data/weed_th_udon_thani.csv --resume     # skip rows already enriched

Cost: ~$0.03 per shop (Places API New, "Pro" SKU — fields include contact info).
For 135 Udon Thani shops: ~$4.
"""

import argparse
import csv
import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.thailand_cannabis.common import DATA_DIR  # noqa: E402

API_URL = "https://places.googleapis.com/v1/places:searchText"
# Field mask determines what data Google returns AND how the request is billed.
# Contact info (phones, opening hours) is the "Pro" SKU.
FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.regularOpeningHours.weekdayDescriptions",
    "places.rating",
    "places.userRatingCount",
    "places.googleMapsUri",
    "places.location",
])
# Google allows 600 QPM = 10 QPS. We pace at ~3 QPS to stay well under the limit.
REQUEST_INTERVAL = 0.35

ENRICH_FIELDS = [
    "google_place_id",
    "google_phone",
    "google_website",
    "google_hours",
    "google_rating",
    "google_user_ratings",
    "google_maps_uri",
    "google_returned_address",
    "google_match_confidence",
]


def build_query(row: dict) -> str:
    """Build a Text Search query from a scraped row."""
    parts = [row.get("name", "").strip()]
    addr = (row.get("address") or "").strip()
    if addr:
        parts.append(addr)
    city = (row.get("city") or "").strip()
    if city and city.lower() not in addr.lower():
        parts.append(city)
    parts.append("Thailand")
    return ", ".join(p for p in parts if p)


def confidence(row: dict, returned_address: str) -> str:
    """Coarse heuristic: does the Google-returned address mention the input city?"""
    if not returned_address:
        return "none"
    city = (row.get("city") or "").lower()
    if city and city in returned_address.lower():
        return "high"
    # Fall back: any token overlap with the input address
    addr_tokens = set((row.get("address") or "").lower().split())
    returned_tokens = set(returned_address.lower().split())
    overlap = addr_tokens & returned_tokens
    if len(overlap) >= 2:
        return "medium"
    return "low"


def search_place(query: str, api_key: str) -> dict | None:
    """Return the first Place result for a text query, or None."""
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    body = {"textQuery": query, "maxResultCount": 1, "languageCode": "en"}
    resp = requests.post(API_URL, headers=headers, json=body, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    places = data.get("places") or []
    return places[0] if places else None


def enrich_row(row: dict, api_key: str) -> dict:
    """Return a copy of row with enrichment fields populated (empty on miss)."""
    out = dict(row)
    for f in ENRICH_FIELDS:
        out.setdefault(f, "")
    query = build_query(row)
    try:
        place = search_place(query, api_key)
    except Exception as e:
        out["google_match_confidence"] = f"error: {e}"
        return out
    if not place:
        out["google_match_confidence"] = "no_result"
        return out

    hours = place.get("regularOpeningHours", {}).get("weekdayDescriptions", [])
    out["google_place_id"] = place.get("id", "")
    out["google_phone"] = (
        place.get("nationalPhoneNumber")
        or place.get("internationalPhoneNumber")
        or ""
    )
    out["google_website"] = place.get("websiteUri", "")
    out["google_hours"] = " | ".join(hours)
    out["google_rating"] = place.get("rating", "")
    out["google_user_ratings"] = place.get("userRatingCount", "")
    out["google_maps_uri"] = place.get("googleMapsUri", "")
    returned_addr = place.get("formattedAddress", "")
    out["google_returned_address"] = returned_addr
    out["google_match_confidence"] = confidence(row, returned_addr)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input_csv", help="CSV produced by scrape_weed_th_detail.py (or similar)")
    parser.add_argument("--limit", type=int, default=None, help="Only process N rows (dry run)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip rows that already have google_place_id in the existing output")
    parser.add_argument("--output", default=None, help="Output CSV path (default: <input>_google.csv)")
    args = parser.parse_args()

    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        print("ERROR: GOOGLE_MAPS_API_KEY env var not set.", file=sys.stderr)
        print('  PowerShell:  $env:GOOGLE_MAPS_API_KEY = "AIza..."', file=sys.stderr)
        return 2

    if not os.path.isabs(args.input_csv):
        args.input_csv = os.path.abspath(args.input_csv)

    with open(args.input_csv, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if args.limit:
        rows = rows[: args.limit]

    out_path = args.output or args.input_csv.replace(".csv", "_google.csv")

    # Resume support: load existing output and skip rows already enriched.
    already_done: dict[str, dict] = {}
    if args.resume and os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("google_place_id"):
                    already_done[r["source_id"]] = r
        print(f"[gplaces] resume: {len(already_done)} rows already enriched, will skip")

    in_fields = list(rows[0].keys()) if rows else []
    out_fields = in_fields + [f for f in ENRICH_FIELDS if f not in in_fields]

    print(f"[gplaces] input={args.input_csv}")
    print(f"[gplaces] rows={len(rows)} interval={REQUEST_INTERVAL}s "
          f"est_runtime~{len(rows) * REQUEST_INTERVAL:.0f}s")
    print(f"[gplaces] output={out_path}")

    results: list[dict] = []
    hits = 0
    misses = 0
    errors = 0
    for i, row in enumerate(rows, 1):
        if row.get("source_id") in already_done:
            results.append(already_done[row["source_id"]])
            continue
        if i > 1:
            time.sleep(REQUEST_INTERVAL)
        enriched = enrich_row(row, api_key)
        results.append(enriched)
        conf = enriched.get("google_match_confidence", "")
        phone = enriched.get("google_phone", "") or "-"
        if conf.startswith("error"):
            errors += 1
        elif conf == "no_result":
            misses += 1
        else:
            hits += 1
        print(f"  [{i}/{len(rows)}] {row.get('name','')[:32]:32s} "
              f"| conf={conf:8s} | phone={phone}")

    # Write output (always rewrite — resume just avoided refetching)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in out_fields})

    with_phone = sum(1 for r in results if r.get("google_phone"))
    print(f"\n[gplaces] hits={hits}  misses={misses}  errors={errors}")
    print(f"[gplaces] with phone: {with_phone}/{len(results)} ({100*with_phone/max(1,len(results)):.0f}%)")
    print(f"[gplaces] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
