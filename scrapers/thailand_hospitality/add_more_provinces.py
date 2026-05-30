"""Add 20 more Thai provinces to the OSM dataset. Same FULL_QUERY as
expand_coverage.py — pulls hotels + restaurants + bars + attractions + spas.

After scraping, re-runs merge_hospitality + aggregate_country + finalize_country.
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
UA = "TH-hospitality/0.3"

# 20 more Thai provinces (most are tourism-adjacent or regional centers)
MORE_CITIES = {
    # South — beaches/islands
    "hatyai":          "6.95,100.40,7.10,100.55",   # Songkhla province, biggest southern city
    "songkhla":        "7.15,100.55,7.30,100.65",
    "phangnga":        "8.40,98.45,8.55,98.55",     # Khao Lak area
    "trang":           "7.50,99.55,7.70,99.70",
    "nakhonsithammarat":"8.40,99.95,8.50,100.05",
    "ranong":          "9.90,98.55,10.05,98.70",
    "satun":           "6.55,100.00,6.70,100.15",
    # North
    "lampang":         "18.25,99.45,18.40,99.55",
    "phrae":           "18.10,100.10,18.20,100.20",
    "uttaradit":       "17.55,100.05,17.70,100.20",
    # Central
    "lopburi":         "14.75,100.55,14.90,100.70",
    "angthong":        "14.50,100.40,14.65,100.55",
    "saraburi":        "14.45,100.85,14.60,101.05",
    "petchaburi":      "12.95,99.90,13.20,100.10",  # gateway to south
    # Isaan (Northeast)
    "ubonratchathani": "15.20,104.80,15.30,104.95",
    "burinam":         "14.95,103.05,15.10,103.20", # Buri Ram
    "surin":           "14.85,103.40,15.00,103.55",
    "yasothon":        "15.75,104.10,15.90,104.25",
    "nakhonphanom":    "17.35,104.75,17.50,104.90",
    "roiet":           "16.00,103.60,16.15,103.75",
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
    print(f"Adding {len(MORE_CITIES)} more Thai provinces to OSM dataset...\n")
    total_added = 0
    failures = []

    for city, bbox in MORE_CITIES.items():
        out_path = os.path.join(DATA_DIR, f"osm_{city}.csv")
        if os.path.exists(out_path):
            print(f"  -- {city}: SKIP (file exists)")
            continue
        print(f"  -- {city} bbox={bbox}")
        q = FULL_QUERY.format(bbox=bbox)
        try:
            r = requests.post(OVERPASS, data={"data": q}, timeout=120,
                              headers={"User-Agent": UA})
        except Exception as e:
            print(f"    ERR: {e}")
            failures.append(city)
            continue
        if r.status_code != 200:
            print(f"    Overpass HTTP {r.status_code}")
            failures.append(city)
            continue
        elements = r.json().get("elements", [])
        rows = [extract_row(e) for e in elements]
        # Dedup
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
        total_added += len(unique)
        time.sleep(2)  # be polite

    print(f"\n[add_more] total POIs added: {total_added}, failures: {failures}")

    # Retry failures once
    if failures:
        print(f"\nRetrying {len(failures)} failed cities...")
        for city in failures:
            bbox = MORE_CITIES[city]
            print(f"  retry {city}")
            q = FULL_QUERY.format(bbox=bbox)
            try:
                r = requests.post(OVERPASS, data={"data": q}, timeout=180,
                                  headers={"User-Agent": UA})
                if r.status_code == 200:
                    elements = r.json().get("elements", [])
                    rows = [extract_row(e) for e in elements]
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
                    print(f"    OK on retry: {len(unique)} POIs")
                else:
                    print(f"    still HTTP {r.status_code}")
            except Exception as e:
                print(f"    still failed: {e}")
            time.sleep(3)

    # Re-merge each new city
    print("\nRunning merge_hospitality for new cities...")
    env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
    for city in MORE_CITIES.keys():
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, "merge_hospitality.py"), city],
            capture_output=True, text=True, env=env, encoding="utf-8", errors="replace"
        )
        tail = (proc.stdout or "").strip().splitlines()
        last = tail[-1] if tail else ""
        ok = "OK" if proc.returncode == 0 else "FAIL"
        print(f"  merge {city}: {ok}  {last[:80]}")

    # Re-aggregate + re-finalize
    print("\nRe-aggregating + re-finalizing...")
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
