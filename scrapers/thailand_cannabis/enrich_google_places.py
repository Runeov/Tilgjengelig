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


def build_query(row: dict, name_col: str = "name", default_city: str = "") -> str:
    """Build a Text Search query from a scraped row.

    `name_col` lets callers point at non-standard column names (e.g. Wongnai's
    `displayName`). `default_city` is appended when the row's `city` field is
    empty (useful when scraping a single-city dataset).
    """
    parts = [(row.get(name_col) or row.get("name") or "").strip()]
    addr = (row.get("address") or "").strip()
    if addr:
        parts.append(addr)
    city = (row.get("city") or "").strip() or default_city.strip()
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


def enrich_row(row: dict, api_key: str, name_col: str = "name", default_city: str = "") -> dict:
    """Return a copy of row with enrichment fields populated (empty on miss)."""
    out = dict(row)
    for f in ENRICH_FIELDS:
        out.setdefault(f, "")
    query = build_query(row, name_col=name_col, default_city=default_city)
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
    parser.add_argument("--name-col", default="name",
                        help="CSV column to use as shop name in the search query "
                             "(default: 'name'; e.g. use 'displayName' for Wongnai CSVs)")
    parser.add_argument("--default-city", default="",
                        help="Append this city when the row has no 'city' field "
                             "(useful for single-city datasets like Wongnai region scrapes)")
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

    # Resume support: scan existing output file for already-enriched source_ids.
    # Streaming append below means existing rows stay where they are; we just skip
    # them during fetch so we don't re-spend on them.
    already_done_sids: set[str] = set()
    file_existed = os.path.exists(out_path)
    if args.resume and file_existed:
        with open(out_path, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("google_place_id") and r.get("source_id"):
                    already_done_sids.add(r["source_id"])
        print(f"[gplaces] resume: {len(already_done_sids)} rows already enriched in {out_path}, will skip")

    in_fields = list(rows[0].keys()) if rows else []
    out_fields = in_fields + [f for f in ENRICH_FIELDS if f not in in_fields]

    new_rows = [r for r in rows if r.get("source_id") not in already_done_sids]
    print(f"[gplaces] input={args.input_csv}")
    print(f"[gplaces] total={len(rows)}  to_fetch={len(new_rows)}  "
          f"interval={REQUEST_INTERVAL}s  est_runtime~{len(new_rows) * REQUEST_INTERVAL:.0f}s "
          f"({len(new_rows) * REQUEST_INTERVAL / 60:.1f} min)")
    print(f"[gplaces] output={out_path}")

    if not new_rows:
        print("[gplaces] nothing to do (all rows already enriched).")
        return 0

    # Streaming append: write each row + flush immediately so a crash never
    # loses prior work. Headers are written only when creating a new file.
    mode = "a" if (args.resume and file_existed) else "w"
    out_f = open(out_path, mode, encoding="utf-8", newline="")
    writer = csv.DictWriter(out_f, fieldnames=out_fields)
    if mode == "w":
        writer.writeheader()
        out_f.flush()

    hits = 0
    misses = 0
    errors = 0
    try:
        for i, row in enumerate(new_rows, 1):
            if i > 1:
                time.sleep(REQUEST_INTERVAL)
            enriched = enrich_row(row, api_key, name_col=args.name_col, default_city=args.default_city)
            conf = enriched.get("google_match_confidence", "")
            phone = enriched.get("google_phone", "") or "-"
            if conf.startswith("error"):
                errors += 1
            elif conf == "no_result":
                misses += 1
            else:
                hits += 1
            writer.writerow({k: enriched.get(k, "") for k in out_fields})
            out_f.flush()
            display = (row.get(args.name_col) or row.get("name") or "")[:32]
            print(f"  [{i}/{len(new_rows)}] {display:32s} "
                  f"| conf={conf:8s} | phone={phone}")
    finally:
        out_f.close()

    print(f"\n[gplaces] this run: hits={hits}  misses={misses}  errors={errors}")
    print(f"[gplaces] cumulative phones in {out_path}: see file or re-run with --resume to see counts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
