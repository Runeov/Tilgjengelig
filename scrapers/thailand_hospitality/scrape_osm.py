"""Scrape OpenStreetMap (via Overpass API) for hospitality POIs in a bounding box.

OSM coverage is sparse for Thai SMBs in some categories (only 2% of restaurants
have FB tags) but DENSE for hotels and tourism attractions:
  - 100+ hotels in Udon Thani area
  - 30+ guesthouses/motels/hostels/apartments
  - 20+ attractions, viewpoints, museums
  - 3-5 nightclubs/pubs/spas
  - Many include real-domain websites + phone numbers

Output: data/osm_<city>.csv with one row per POI.

Usage:
  python scrape_osm.py udonthani
  python scrape_osm.py bangkok --bbox 13.5,100.4,14.0,100.9

  python scrape_osm.py --list-cities   # show known bboxes
"""

import argparse
import csv
import os
import sys

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = "TH-hospitality-research/0.1"

# Bounding boxes for cities we care about. (south, west, north, east).
KNOWN_BBOXES = {
    "udonthani":   "17.0,102.5,17.7,103.3",
    "bangkok":     "13.5,100.4,14.0,100.9",
    "chiangmai":   "18.65,98.85,18.95,99.10",
    "phuket":      "7.7,98.2,8.2,98.5",
    "pattaya":     "12.8,100.85,13.0,101.0",
    "krabi":       "8.0,98.85,8.15,98.95",
    "huahin":      "12.4,99.85,12.85,100.05",
    "chiangrai":   "19.85,99.75,20.05,99.95",
    "khonkaen":    "16.30,102.70,16.55,103.00",
    "korat":       "14.85,101.95,15.10,102.20",
    "surat-thani": "8.95,99.25,9.25,99.50",
    "1009-pattaya": "12.8,100.85,13.0,101.0",  # same as pattaya
}

# OSM amenity/tourism tags to query. Restaurants/cafés are intentionally NOT
# here — we get those from Wongnai which has way better coverage.
QUERY_TEMPLATE = """
[out:json][timeout:90];
(
  node["tourism"~"hotel|guest_house|hostel|motel|apartment|resort|attraction|viewpoint|museum|gallery|theme_park"]({bbox});
  way["tourism"~"hotel|guest_house|hostel|motel|apartment|resort|attraction|viewpoint|museum|gallery|theme_park"]({bbox});
  node["amenity"~"nightclub|pub|spa|bar"]({bbox});
  way["amenity"~"nightclub|pub|spa|bar"]({bbox});
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
    "cuisine",  # for bars/pubs that have it
    "wheelchair", "operator",
]


def get_lat_lng(e: dict) -> tuple[float | None, float | None]:
    if e.get("type") == "node":
        return e.get("lat"), e.get("lon")
    # Ways have a `center` if we use `out center`. Without that, use bounds midpoint.
    center = e.get("center") or {}
    if center:
        return center.get("lat"), center.get("lon")
    bounds = e.get("bounds") or {}
    if bounds:
        return ((bounds["minlat"] + bounds["maxlat"]) / 2,
                (bounds["minlon"] + bounds["maxlon"]) / 2)
    return None, None


def address_from_tags(t: dict) -> str:
    parts = []
    for k in ("addr:housenumber", "addr:street", "addr:subdistrict",
              "addr:district", "addr:city", "addr:province", "addr:postcode"):
        v = t.get(k)
        if v:
            parts.append(v)
    return ", ".join(parts)


def extract_row(e: dict) -> dict:
    t = e.get("tags") or {}
    lat, lng = get_lat_lng(e)
    category = "tourism" if t.get("tourism") else "amenity" if t.get("amenity") else "?"
    subcategory = t.get("tourism") or t.get("amenity") or ""
    # Find a FB URL from contact: tags or website-with-facebook.com
    fb = t.get("contact:facebook") or ""
    if not fb and "facebook.com" in (t.get("website") or "").lower():
        fb = t.get("website") or ""
    return {
        "osm_id": str(e.get("id", "")),
        "osm_type": e.get("type", ""),
        "category": category,
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
        "line_id": t.get("contact:line") or t.get("line") or "",
        "email": t.get("contact:email") or t.get("email") or "",
        "opening_hours": t.get("opening_hours", ""),
        "address_full": address_from_tags(t),
        "stars": t.get("stars", ""),
        "cuisine": t.get("cuisine", ""),
        "wheelchair": t.get("wheelchair", ""),
        "operator": t.get("operator", ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("city", nargs="?", help="City slug (e.g. 'udonthani')")
    parser.add_argument("--bbox", help="Override bounding box: 'south,west,north,east'")
    parser.add_argument("--list-cities", action="store_true")
    args = parser.parse_args()

    if args.list_cities:
        for k, v in KNOWN_BBOXES.items():
            print(f"  {k:<15}  {v}")
        return 0
    if not args.city:
        parser.error("city argument required (or use --list-cities)")

    bbox = args.bbox or KNOWN_BBOXES.get(args.city.lower())
    if not bbox:
        parser.error(f"No bbox known for {args.city!r}. Provide --bbox 'south,west,north,east'.")

    print(f"[osm] querying Overpass for {args.city} bbox={bbox}")
    query = QUERY_TEMPLATE.format(bbox=bbox)
    r = requests.post(OVERPASS, data={"data": query}, timeout=120,
                      headers={"User-Agent": UA})
    if r.status_code != 200:
        print(f"  Overpass HTTP {r.status_code}: {r.text[:300]}")
        return 1
    data = r.json()
    elements = data.get("elements", [])
    print(f"[osm] received {len(elements):,} POIs")

    rows = [extract_row(e) for e in elements]
    # Optional dedupe — OSM can have duplicate node + way for the same POI
    seen = set()
    unique = []
    for r0 in rows:
        key = (r0["name"].strip().lower(), round(float(r0["lat"] or 0), 5),
               round(float(r0["lng"] or 0), 5))
        if key in seen:
            continue
        seen.add(key)
        unique.append(r0)
    print(f"[osm] after dedup by (name, lat, lng): {len(unique)}")

    out_path = os.path.join(DATA_DIR, f"osm_{args.city.lower()}.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r0 in unique:
            writer.writerow(r0)
    print(f"[osm] wrote {out_path}")

    # Quick summary
    from collections import Counter
    by_sub = Counter(r["subcategory"] for r in unique)
    print("\n[osm] breakdown:")
    for k, n in by_sub.most_common():
        print(f"  {n:>4}  {k}")
    with_phone = sum(1 for r in unique if r["phone"])
    with_web = sum(1 for r in unique if r["website"])
    with_fb = sum(1 for r in unique if r["facebook"])
    print(f"\n[osm] field coverage: phone={with_phone}/{len(unique)} "
          f"website={with_web}/{len(unique)} facebook={with_fb}/{len(unique)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
