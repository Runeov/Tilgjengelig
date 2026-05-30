"""Fill the restaurant/cafe gap for cities where Wongnai is rate-limited.

For the 9 cities where Wongnai bulk scrape failed (everyone except Bangkok and
Udon Thani), pull restaurants + cafes + fast_food from OSM and APPEND to the
existing osm_<city>.csv. OSM coverage is sparse vs Wongnai (Thai contributors
don't populate many tags) but it's something.

After running this, re-run merge_hospitality.py for each city to incorporate
the new rows.

Usage:
  python osm_restaurants_supplement.py            # default: 9 cities missing Wongnai
  python osm_restaurants_supplement.py --cities phuket,krabi
"""

import argparse
import csv
import os
import sys

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
OVERPASS = "https://overpass-api.de/api/interpreter"

# Same as scrape_osm.py KNOWN_BBOXES
KNOWN_BBOXES = {
    "phuket":      "7.7,98.2,8.2,98.5",
    "chiangmai":   "18.65,98.85,18.95,99.10",
    "1009-pattaya": "12.8,100.85,13.0,101.0",
    "krabi":       "8.0,98.85,8.15,98.95",
    "surat-thani": "8.95,99.25,9.25,99.50",
    "huahin":      "12.4,99.85,12.85,100.05",
    "chiangrai":   "19.85,99.75,20.05,99.95",
    "khonkaen":    "16.30,102.70,16.55,103.00",
    "korat":       "14.85,101.95,15.10,102.20",
}

# Default = cities missing Wongnai bulk
DEFAULT_CITIES = list(KNOWN_BBOXES.keys())

# Restaurant + cafe + fast_food OSM amenities (the gap we need to fill)
QUERY_TEMPLATE = """
[out:json][timeout:90];
(
  node["amenity"~"restaurant|cafe|fast_food|food_court|biergarten|ice_cream"]({bbox});
  way["amenity"~"restaurant|cafe|fast_food|food_court|biergarten|ice_cream"]({bbox});
);
out body;
"""

# Same schema as scrape_osm.py
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
    center = e.get("center") or {}
    if center:
        return center.get("lat"), center.get("lon")
    return None, None


def address_from_tags(t):
    parts = []
    for k in ("addr:housenumber", "addr:street", "addr:subdistrict",
              "addr:district", "addr:city", "addr:province", "addr:postcode"):
        v = t.get(k)
        if v:
            parts.append(v)
    return ", ".join(parts)


def extract_row(e):
    t = e.get("tags") or {}
    lat, lng = get_lat_lng(e)
    subcategory = t.get("amenity") or ""
    fb = t.get("contact:facebook") or ""
    if not fb and "facebook.com" in (t.get("website") or "").lower():
        fb = t.get("website") or ""
    return {
        "osm_id": str(e.get("id", "")),
        "osm_type": e.get("type", ""),
        "category": "amenity",
        "subcategory": subcategory,
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
        "stars": "",
        "cuisine": t.get("cuisine", ""),
        "wheelchair": t.get("wheelchair", ""),
        "operator": t.get("operator", ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cities", help="Comma-separated slugs (default: 9 Wongnai-missing cities)")
    args = parser.parse_args()

    cities = ([c.strip() for c in args.cities.split(",")] if args.cities else DEFAULT_CITIES)
    print(f"[supplement] {len(cities)} cities: {', '.join(cities)}")

    for city in cities:
        bbox = KNOWN_BBOXES.get(city)
        if not bbox:
            print(f"  {city}: NO BBOX known, skipping")
            continue
        print(f"\n  === {city} (bbox {bbox}) ===")
        query = QUERY_TEMPLATE.format(bbox=bbox)
        try:
            r = requests.post(OVERPASS, data={"data": query}, timeout=120,
                              headers={"User-Agent": "TH-hospitality-supp/0.1"})
        except Exception as e:
            print(f"    ERR Overpass: {e}")
            continue
        if r.status_code != 200:
            print(f"    Overpass HTTP {r.status_code}: {r.text[:200]}")
            continue
        elements = r.json().get("elements", [])
        rows = [extract_row(e) for e in elements]
        # Dedup with existing osm_<city>.csv: skip rows whose osm_id is already there
        existing_path = os.path.join(DATA_DIR, f"osm_{city}.csv")
        existing_ids: set = set()
        if os.path.exists(existing_path):
            with open(existing_path, "r", encoding="utf-8", newline="") as f:
                for r0 in csv.DictReader(f):
                    if r0.get("osm_id"):
                        existing_ids.add(r0["osm_id"])
        new_rows = [r for r in rows if r["osm_id"] not in existing_ids]
        print(f"    fetched {len(elements)} restaurants/cafes; "
              f"new vs existing osm_{city}.csv: {len(new_rows)}")

        if new_rows:
            mode = "a" if os.path.exists(existing_path) else "w"
            with open(existing_path, mode, encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                if mode == "w":
                    writer.writeheader()
                for r0 in new_rows:
                    writer.writerow(r0)
            print(f"    appended to {existing_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
