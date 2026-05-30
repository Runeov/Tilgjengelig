"""Add 4 Isaan provinces neighboring Udon Thani:
  - Nong Khai (north, on Laos border, tourist gateway)
  - Sakon Nakhon (east)
  - Loei (west, mountains/Phu Kradueng)
  - Nong Bua Lam Phu (just south of Udon Thani)

These are all Udon-Thani-adjacent and feed the same regional hospitality market.
"""

import csv
import os
import subprocess
import sys
import time

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
OVERPASS = "https://overpass-api.de/api/interpreter"
UA = "TH-hospitality/0.4"

CITIES = {
    "nongkhai":         "17.80,102.60,17.95,102.80",  # city of Nong Khai
    "sakonnakhon":      "17.10,104.10,17.20,104.20",  # Sakon Nakhon city
    "loei":             "17.45,101.60,17.55,101.80",  # Loei city
    "nongbualamphu":    "17.15,102.35,17.30,102.50",  # Nong Bua Lam Phu city
}

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


def main() -> int:
    print(f"Adding {len(CITIES)} Isaan neighbors of Udon Thani...")
    for city, bbox in CITIES.items():
        out_path = os.path.join(DATA_DIR, f"osm_{city}.csv")
        if os.path.exists(out_path):
            print(f"  -- {city}: exists, skipping")
            continue
        print(f"  -- {city} bbox={bbox}")
        try:
            r = requests.post(OVERPASS, data={"data": FULL_QUERY.format(bbox=bbox)},
                              timeout=120, headers={"User-Agent": UA})
            r.raise_for_status()
        except Exception as e:
            print(f"    ERR: {e}")
            continue
        elements = r.json().get("elements", [])
        rows = [extract_row(e) for e in elements]
        seen = set(); unique = []
        for r0 in rows:
            if r0["osm_id"] not in seen:
                seen.add(r0["osm_id"]); unique.append(r0)
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            w.writeheader()
            for r0 in unique:
                w.writerow(r0)
        print(f"    {len(unique)} POIs → osm_{city}.csv")
        time.sleep(2)

    # Merge each new city
    env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
    for city in CITIES.keys():
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, "merge_hospitality.py"), city],
            capture_output=True, text=True, env=env, encoding="utf-8", errors="replace"
        )
        tail = (proc.stdout or "").strip().splitlines()
        last = tail[-1] if tail else ""
        print(f"  merge {city}: {last[:80]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
