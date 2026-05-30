"""Re-query OSM for Udon Thani with a much wider province-level bbox,
append any new POIs not already in osm_udonthani.csv."""

import csv
import os
import sys

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
OVERPASS = "https://overpass-api.de/api/interpreter"
UA = "TH-hospitality/0.5"

# Full Udon Thani province bbox (was: 17.0,102.5,17.7,103.3 city + surroundings)
PROVINCE_BBOX = "17.00,102.30,18.00,103.50"

FULL_QUERY = """
[out:json][timeout:120];
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
        "category": cat, "subcategory": sub,
        "name": t.get("name", ""),
        "name_en": t.get("name:en", ""), "name_th": t.get("name:th", ""),
        "lat": lat if lat is not None else "",
        "lng": lng if lng is not None else "",
        "phone": t.get("contact:phone") or t.get("phone") or "",
        "website": t.get("contact:website") or t.get("website") or t.get("url") or "",
        "facebook": fb, "instagram": t.get("contact:instagram") or "",
        "line_id": t.get("contact:line") or "",
        "email": t.get("contact:email") or t.get("email") or "",
        "opening_hours": t.get("opening_hours", ""),
        "address_full": address_from_tags(t),
        "stars": t.get("stars", ""), "cuisine": t.get("cuisine", ""),
        "wheelchair": t.get("wheelchair", ""), "operator": t.get("operator", ""),
    }


print(f"Querying Overpass for Udon Thani province bbox={PROVINCE_BBOX}")
r = requests.post(OVERPASS, data={"data": FULL_QUERY.format(bbox=PROVINCE_BBOX)},
                  timeout=180, headers={"User-Agent": UA})
if r.status_code != 200:
    print(f"Overpass HTTP {r.status_code}: {r.text[:200]}")
    sys.exit(1)
elements = r.json().get("elements", [])
rows = [extract_row(e) for e in elements]
print(f"Got {len(rows)} POIs from province bbox")

# Append non-duplicate rows to osm_udonthani.csv
out_path = os.path.join(DATA_DIR, "osm_udonthani.csv")
existing_ids: set = set()
with open(out_path, "r", encoding="utf-8", newline="") as f:
    for r0 in csv.DictReader(f):
        if r0.get("osm_id"):
            existing_ids.add(r0["osm_id"])
print(f"Existing osm_udonthani.csv has {len(existing_ids)} rows")

new = [r for r in rows if r["osm_id"] not in existing_ids]
print(f"New (not already in CSV): {len(new)}")

with open(out_path, "a", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
    for r0 in new:
        writer.writerow(r0)
print(f"Appended {len(new)} new POIs → {out_path}")
