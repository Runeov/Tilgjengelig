"""Probe OpenStreetMap (via Overpass API) for Udon Thani restaurants/bars
and check whether they have facebook/instagram/phone tags."""

import json
import requests

OVERPASS = "https://overpass-api.de/api/interpreter"

# Bounding box for Udon Thani city + surrounding area
# Approx: 17.0–17.6 N, 102.5–103.2 E
BBOX = "17.0,102.5,17.7,103.3"

# Overpass QL: restaurants + bars + cafes within bbox, with any contact tag
QUERY = f"""
[out:json][timeout:60];
(
  node["amenity"~"restaurant|bar|cafe|fast_food|pub|biergarten|food_court"]({BBOX});
  way["amenity"~"restaurant|bar|cafe|fast_food|pub|biergarten|food_court"]({BBOX});
);
out body;
"""

print(f"Query: amenity=restaurant|bar|cafe|fast_food|pub in {BBOX}")
r = requests.post(OVERPASS, data={"data": QUERY}, timeout=90,
                  headers={"User-Agent": "TH-hospitality-research/0.1"})
print(f"HTTP {r.status_code}, {len(r.text):,} bytes")
if r.status_code != 200:
    print(r.text[:500])
    raise SystemExit(1)
data = r.json()
elements = data.get("elements", [])
print(f"Total POIs: {len(elements):,}")

# Field coverage stats
fields = ["name", "contact:facebook", "contact:instagram", "contact:line",
          "website", "url", "contact:phone", "phone", "contact:website",
          "contact:email", "email", "amenity", "cuisine", "opening_hours"]
counts = {f: 0 for f in fields}
amenities = {}
for el in elements:
    tags = el.get("tags") or {}
    for f in fields:
        if tags.get(f):
            counts[f] += 1
    amenities[tags.get("amenity", "?")] = amenities.get(tags.get("amenity", "?"), 0) + 1

print(f"\nAmenity breakdown:")
for amenity, n in sorted(amenities.items(), key=lambda kv: -kv[1]):
    print(f"  {n:>4}  {amenity}")

print(f"\nField coverage:")
for f, n in counts.items():
    pct = (100 * n / len(elements)) if elements else 0
    print(f"  {n:>4} ({pct:>4.0f}%)  {f}")

# Show a few sample entities with FB tag
print("\nSample POIs with contact:facebook:")
with_fb = [e for e in elements if (e.get("tags") or {}).get("contact:facebook")][:5]
for e in with_fb:
    t = e.get("tags") or {}
    print(f"  - {t.get('name', '?')[:30]:<30} | fb: {t.get('contact:facebook', '')[:50]}")
