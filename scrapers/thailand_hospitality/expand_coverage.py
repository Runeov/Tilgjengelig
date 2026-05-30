"""Expand coverage with two operations:

  1. Add MORE OSM categories to existing cities — spa, fitness, leisure,
     tour operators, liquor stores, marketplaces. These are tourism/B2B-
     relevant SMBs we missed in earlier scrapes.

  2. Add 6 NEW Thai tourist/regional cities — full OSM scrape (hotels +
     restaurants + bars + everything we scrape for the original 11).

Output appends to existing osm_<city>.csv files / creates new ones, then
re-runs merge_hospitality + aggregate_country + finalize_country at the end.
"""

import argparse
import csv
import os
import subprocess
import sys
import time

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
OVERPASS = "https://overpass-api.de/api/interpreter"
UA = "TH-hospitality/0.2"

# Existing cities — add new categories to their osm_<city>.csv
EXISTING_CITIES = {
    "udonthani":     "17.0,102.5,17.7,103.3",
    "bangkok":       "13.5,100.4,14.0,100.9",
    "chiangmai":     "18.65,98.85,18.95,99.10",
    "phuket":        "7.7,98.2,8.2,98.5",
    "1009-pattaya":  "12.8,100.85,13.0,101.0",
    "krabi":         "8.0,98.85,8.15,98.95",
    "huahin":        "12.4,99.85,12.85,100.05",
    "chiangrai":     "19.85,99.75,20.05,99.95",
    "khonkaen":      "16.30,102.70,16.55,103.00",
    "korat":         "14.85,101.95,15.10,102.20",
    "surat-thani":   "8.95,99.25,9.25,99.50",
}

# New cities to scrape full OSM hospitality + restaurants
NEW_CITIES = {
    "kanchanaburi":  "13.95,99.40,14.20,99.65",  # west TH, tourist (River Kwai)
    "maehongson":    "19.20,97.85,19.45,98.20",  # north TH, tourist
    "sukhothai":     "17.00,99.75,17.15,99.95",  # north central, UNESCO
    "trat":          "12.20,102.40,12.40,102.65", # east coast, Koh Chang gateway
    "phitsanulok":   "16.75,100.20,16.95,100.40", # north central
    "nan":           "18.70,100.70,18.85,100.85", # north, growing tourist
    "pai":           "19.32,98.40,19.40,98.50",   # Mae Hong Son tourist hotspot
}

# Extra B2B-relevant categories to ADD to existing cities (already-scraped have
# hotels/restaurants/bars; supplementing with the rest of hospitality vertical)
EXTRA_QUERY = """
[out:json][timeout:90];
(
  node["amenity"~"marketplace|cinema|theatre|arts_centre|ice_cream"]({bbox});
  way["amenity"~"marketplace|cinema|theatre|arts_centre|ice_cream"]({bbox});
  node["shop"~"alcohol|beverages|massage"]({bbox});
  way["shop"~"alcohol|beverages|massage"]({bbox});
  node["leisure"~"fitness_centre|sports_centre|water_park|resort|golf_course"]({bbox});
  way["leisure"~"fitness_centre|sports_centre|water_park|resort|golf_course"]({bbox});
  node["tourism"="information"]({bbox});
  way["tourism"="information"]({bbox});
);
out body;
"""

# Full hospitality query (same as scrape_osm.py + supplements combined)
FULL_QUERY = """
[out:json][timeout:90];
(
  node["tourism"~"hotel|guest_house|hostel|motel|apartment|resort|attraction|viewpoint|museum|gallery|theme_park|information"]({bbox});
  way["tourism"~"hotel|guest_house|hostel|motel|apartment|resort|attraction|viewpoint|museum|gallery|theme_park|information"]({bbox});
  node["amenity"~"nightclub|pub|spa|bar|restaurant|cafe|fast_food|food_court|biergarten|ice_cream|marketplace|cinema|theatre|arts_centre"]({bbox});
  way["amenity"~"nightclub|pub|spa|bar|restaurant|cafe|fast_food|food_court|biergarten|ice_cream|marketplace|cinema|theatre|arts_centre"]({bbox});
  node["shop"~"alcohol|beverages|massage"]({bbox});
  way["shop"~"alcohol|beverages|massage"]({bbox});
  node["leisure"~"fitness_centre|sports_centre|water_park|resort|golf_course"]({bbox});
  way["leisure"~"fitness_centre|sports_centre|water_park|resort|golf_course"]({bbox});
);
out body;
"""

CSV_FIELDS = [
    "osm_id", "osm_type", "category", "subcategory",
    "name", "name_en", "name_th",
    "lat", "lng",
    "phone", "website",
    "facebook", "instagram", "line_id",
    "email", "opening_hours",
    "address_full", "stars",
    "cuisine",
    "wheelchair", "operator",
]


def get_lat_lng(e):
    if e.get("type") == "node":
        return e.get("lat"), e.get("lon")
    c = e.get("center") or {}
    return (c.get("lat"), c.get("lon")) if c else (None, None)


def address_from_tags(t):
    return ", ".join(t.get(k) for k in (
        "addr:housenumber", "addr:street", "addr:subdistrict",
        "addr:district", "addr:city", "addr:province", "addr:postcode"
    ) if t.get(k))


def extract_row(e):
    t = e.get("tags") or {}
    lat, lng = get_lat_lng(e)
    cat = ("tourism" if t.get("tourism") else
           "shop" if t.get("shop") else
           "leisure" if t.get("leisure") else
           "amenity" if t.get("amenity") else "?")
    sub = t.get("tourism") or t.get("shop") or t.get("leisure") or t.get("amenity") or ""
    fb = t.get("contact:facebook") or ""
    if not fb and "facebook.com" in (t.get("website") or "").lower():
        fb = t.get("website") or ""
    return {
        "osm_id": str(e.get("id", "")),
        "osm_type": e.get("type", ""),
        "category": cat,
        "subcategory": sub,
        "name": t.get("name", ""),
        "name_en": t.get("name:en", ""),
        "name_th": t.get("name:th", ""),
        "lat": lat if lat is not None else "",
        "lng": lng if lng is not None else "",
        "phone": t.get("contact:phone") or t.get("phone") or "",
        "website": t.get("contact:website") or t.get("website") or t.get("url") or "",
        "facebook": fb,
        "instagram": t.get("contact:instagram") or "",
        "line_id": t.get("contact:line") or "",
        "email": t.get("contact:email") or t.get("email") or "",
        "opening_hours": t.get("opening_hours", ""),
        "address_full": address_from_tags(t),
        "stars": t.get("stars", ""),
        "cuisine": t.get("cuisine", ""),
        "wheelchair": t.get("wheelchair", ""),
        "operator": t.get("operator", ""),
    }


def query_overpass(query: str, bbox: str) -> list[dict]:
    q = query.format(bbox=bbox)
    r = requests.post(OVERPASS, data={"data": q}, timeout=120, headers={"User-Agent": UA})
    if r.status_code != 200:
        print(f"    Overpass HTTP {r.status_code}: {r.text[:200]}")
        return []
    return r.json().get("elements", [])


def append_to_osm(city: str, rows: list[dict]) -> int:
    """Append rows to osm_<city>.csv, deduping by osm_id. Returns count of new rows added."""
    out_path = os.path.join(DATA_DIR, f"osm_{city}.csv")
    existing_ids: set = set()
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8", newline="") as f:
            for r0 in csv.DictReader(f):
                if r0.get("osm_id"):
                    existing_ids.add(r0["osm_id"])
    new = [r for r in rows if r["osm_id"] not in existing_ids]
    if not new:
        return 0
    mode = "a" if os.path.exists(out_path) else "w"
    with open(out_path, mode, encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if mode == "w":
            writer.writeheader()
        for r0 in new:
            writer.writerow(r0)
    return len(new)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-existing", action="store_true",
                        help="Don't add extra categories to existing cities")
    parser.add_argument("--skip-new", action="store_true",
                        help="Don't scrape new cities")
    parser.add_argument("--skip-merge", action="store_true",
                        help="Don't re-merge / re-aggregate at end")
    args = parser.parse_args()

    grand_added = 0

    # === 1. Extra categories on existing 11 cities ===
    if not args.skip_existing:
        print(f"\n{'='*60}\n  Phase A: extra OSM categories on existing cities\n{'='*60}")
        for city, bbox in EXISTING_CITIES.items():
            print(f"\n  -- {city} (extras only) bbox={bbox}")
            elements = query_overpass(EXTRA_QUERY, bbox)
            rows = [extract_row(e) for e in elements]
            added = append_to_osm(city, rows)
            print(f"    fetched {len(elements)} extra POIs, added {added} new to osm_{city}.csv")
            grand_added += added
            time.sleep(2)  # be polite to Overpass

    # === 2. Full OSM scrape for new cities ===
    if not args.skip_new:
        print(f"\n{'='*60}\n  Phase B: full OSM scrape for new cities\n{'='*60}")
        for city, bbox in NEW_CITIES.items():
            print(f"\n  -- {city} (FULL) bbox={bbox}")
            elements = query_overpass(FULL_QUERY, bbox)
            rows = [extract_row(e) for e in elements]
            # Dedup by (osm_id) within this fetch
            seen = set(); unique = []
            for r0 in rows:
                if r0["osm_id"] not in seen:
                    seen.add(r0["osm_id"]); unique.append(r0)
            out_path = os.path.join(DATA_DIR, f"osm_{city}.csv")
            with open(out_path, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                w.writeheader()
                for r0 in unique:
                    w.writerow(r0)
            print(f"    {len(unique)} unique POIs → osm_{city}.csv")
            grand_added += len(unique)
            time.sleep(3)

    print(f"\n[expand] total rows added across all operations: {grand_added}")

    # === 3. Re-merge + re-aggregate + re-finalize ===
    if not args.skip_merge:
        all_cities = list(EXISTING_CITIES.keys())
        if not args.skip_new:
            all_cities += list(NEW_CITIES.keys())
        print(f"\n{'='*60}\n  Phase C: re-merge {len(all_cities)} cities\n{'='*60}")
        env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
        for city in all_cities:
            proc = subprocess.run(
                [sys.executable, os.path.join(SCRIPT_DIR, "merge_hospitality.py"), city],
                capture_output=True, text=True, env=env, encoding="utf-8", errors="replace"
            )
            ok = "OK" if proc.returncode == 0 else "FAIL"
            tail = (proc.stdout or "").strip().splitlines()
            last = tail[-1] if tail else ""
            print(f"  merge {city}: {ok}  {last[:80]}")
        print("\n[expand] running aggregate + finalize...")
        for script in ("aggregate_country.py", "finalize_country.py"):
            proc = subprocess.run(
                [sys.executable, os.path.join(SCRIPT_DIR, script)],
                capture_output=True, text=True, env=env, encoding="utf-8", errors="replace"
            )
            for line in (proc.stdout or "").strip().splitlines()[-3:]:
                print(f"    {line}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
