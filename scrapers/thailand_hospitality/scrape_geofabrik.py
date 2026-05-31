"""Scrape OpenStreetMap from a Geofabrik bulk extract (offline .osm.pbf).

Drop-in alternative to scrape_osm.py that reads a downloaded Thailand extract
instead of hitting the Overpass API per province. One download covers all 77
provinces with **no rate limit and no 403 risk** — the highest-leverage way to
cover "the rest of Thailand".

It reuses scrape_osm's tag->venue_type mapping and CSV schema, so output is a
byte-compatible `data/osm_<slug>.csv` that merge_hospitality.py already consumes.

Workflow:
  # 1. Download the national extract once (needs egress to download.geofabrik.de):
  python scrape_geofabrik.py --download

  # 2. Parse the whole country (one CSV, all venue_types incl. bar/show):
  python scrape_geofabrik.py --slug thailand

  # 3. Or restrict to a province bbox (same 'south,west,north,east' as scrape_osm)
  #    to produce a per-province file the merge pipeline picks up:
  python scrape_geofabrik.py --slug rayong --bbox 12.5,101.0,13.2,101.9

  # Verify the reused tag->venue_type logic without any network/deps:
  python scrape_geofabrik.py --selftest

Requires: pip install pyrosm   (parses .osm.pbf; pulls in geopandas/shapely)

NOTE: the pyrosm column/tag layout should be confirmed on the first real run —
the adapter below merges pyrosm's promoted tag columns with its `tags` dict and
normalises the contact:* keys scrape_osm expects, but pyrosm versions differ in
exactly which tags they promote.
"""

import argparse
import csv
import os
import sys

# Reuse the canonical schema + classification from the live OSM scraper so the
# two sources never drift. extract_row() consumes an Overpass-shaped element
# dict: {"type","id","tags":{...},"lat","lon"/"center":{...}}.
from scrape_osm import (
    CSV_FIELDS,
    DATA_DIR,
    extract_row,
    venue_type_for,
    BAR_SUBCATS,
    SHOW_SUBCATS,
)

GEOFABRIK_URL = "https://download.geofabrik.de/asia/thailand-latest.osm.pbf"
DEFAULT_PBF = os.path.join(DATA_DIR, "thailand-latest.osm.pbf")

# Same tag selection as scrape_osm's QUERY_TEMPLATE, expressed as a pyrosm
# custom_filter (key -> list of accepted values). Restaurants/cafes are
# intentionally excluded (Wongnai covers those better).
CUSTOM_FILTER = {
    "tourism": ["hotel", "guest_house", "hostel", "motel", "apartment", "resort",
                "attraction", "viewpoint", "museum", "gallery", "theme_park"],
    "amenity": ["nightclub", "pub", "spa", "bar", "theatre", "cinema",
                "arts_centre", "stripclub"],
    "leisure": ["stadium", "dance", "adult_gaming_centre"],
    "sport": ["muay_thai", "boxing", "martial_arts"],
}


def _download(dest: str) -> int:
    import requests
    print(f"[geofabrik] downloading {GEOFABRIK_URL}")
    print(f"[geofabrik] -> {dest}  (this is a few hundred MB)")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with requests.get(GEOFABRIK_URL, stream=True, timeout=600,
                      headers={"User-Agent": "TH-hospitality-research/0.1"}) as r:
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}: {r.text[:200]}")
            return 1
        total = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                total += len(chunk)
                print(f"\r  {total / 1e6:,.0f} MB", end="", flush=True)
    print(f"\n[geofabrik] saved {total / 1e6:,.0f} MB")
    return 0


def _row_to_element(row) -> dict:
    """Adapt one pyrosm GeoDataFrame row into an Overpass-shaped element dict.

    pyrosm promotes common tags to columns and stuffs the rest into a `tags`
    dict. We merge both, then hand the result to scrape_osm.extract_row so the
    field extraction / venue_type logic is shared with the live scraper.
    """
    # pandas Series -> plain dict, dropping NaNs.
    import math
    raw = {}
    for k, v in row.items():
        if v is None:
            continue
        if isinstance(v, float) and math.isnan(v):
            continue
        raw[k] = v

    # pyrosm's leftover tags live under "tags" (dict, or a JSON string).
    tags: dict = {}
    extra = raw.pop("tags", None)
    if isinstance(extra, dict):
        tags.update(extra)
    elif isinstance(extra, str) and extra.strip().startswith("{"):
        import json
        try:
            tags.update(json.loads(extra))
        except ValueError:
            pass

    # Promote scalar columns (name, amenity, phone, opening_hours, addr:*, ...)
    # into the tag dict; skip geometry/bookkeeping columns.
    skip = {"geometry", "id", "osm_type", "version", "timestamp", "changeset"}
    for k, v in raw.items():
        if k in skip:
            continue
        tags.setdefault(k, v)

    # Normalise the few contact keys extract_row reads but pyrosm may flatten.
    for canonical, aliases in {
        "contact:phone": ("contact_phone",),
        "contact:website": ("contact_website",),
        "contact:facebook": ("contact_facebook",),
        "contact:instagram": ("contact_instagram",),
        "contact:email": ("contact_email",),
        "name:en": ("name_en",),
        "name:th": ("name_th",),
    }.items():
        if canonical not in tags:
            for a in aliases:
                if a in tags:
                    tags[canonical] = tags[a]
                    break

    geom = raw.get("geometry")
    lat = lng = None
    if geom is not None:
        try:
            c = geom.centroid
            lat, lng = c.y, c.x
        except Exception:
            pass

    return {
        "type": raw.get("osm_type", "node"),
        "id": raw.get("id", ""),
        "tags": tags,
        "lat": lat,
        "lon": lng,
    }


def _parse(pbf_path: str, bbox: str | None):
    """Return a list of extract_row dicts from the pbf (optionally bbox-clipped)."""
    try:
        from pyrosm import OSM
    except ImportError:
        print("[geofabrik] pyrosm not installed. Run: pip install pyrosm")
        raise

    bounding_box = None
    if bbox:
        # scrape_osm uses 'south,west,north,east'; pyrosm wants [w, s, e, n].
        s, w, n, e = (float(x) for x in bbox.split(","))
        bounding_box = [w, s, e, n]

    print(f"[geofabrik] parsing {pbf_path}"
          + (f"  bbox={bbox}" if bbox else "  (whole extract)"))
    osm = OSM(pbf_path, bounding_box=bounding_box)
    gdf = osm.get_data_by_custom_criteria(
        custom_filter=CUSTOM_FILTER,
        filter_type="keep",
        keep_nodes=True,
        keep_ways=True,
        keep_relations=True,
    )
    if gdf is None or len(gdf) == 0:
        print("[geofabrik] no matching POIs found")
        return []
    print(f"[geofabrik] {len(gdf):,} raw POIs; mapping to schema...")
    return [extract_row(_row_to_element(row)) for _, row in gdf.iterrows()]


def _dedupe(rows: list[dict]) -> list[dict]:
    """Dedupe by (name, lat, lng) — same rule as scrape_osm."""
    seen, unique = set(), []
    for r in rows:
        try:
            key = (r["name"].strip().lower(),
                   round(float(r["lat"] or 0), 5),
                   round(float(r["lng"] or 0), 5))
        except (TypeError, ValueError):
            key = (r["name"].strip().lower(), r["lat"], r["lng"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def _write(rows: list[dict], slug: str) -> str:
    out_path = os.path.join(DATA_DIR, f"osm_{slug.lower()}.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in CSV_FIELDS})
    return out_path


def _selftest() -> int:
    """Exercise the reused tag->venue_type mapping with no network or pyrosm."""
    cases = {
        "bar": "bar", "pub": "bar", "nightclub": "bar", "stripclub": "bar",
        "theatre": "show", "cinema": "show", "muay_thai": "show",
        "theme_park": "show", "stadium": "show",
        "hotel": "lodging", "hostel": "lodging",
        "attraction": "attraction", "spa": "spa", "restaurant": "",
    }
    ok = True
    for sub, expected in cases.items():
        got = venue_type_for(sub)
        flag = "ok " if got == expected else "BAD"
        if got != expected:
            ok = False
        print(f"  [{flag}] {sub:<12} -> {got!r}  (want {expected!r})")
    # Sanity: every filtered subcategory classifies as bar/show or a known type.
    bars_shows = BAR_SUBCATS | SHOW_SUBCATS
    print(f"\n[selftest] {len(bars_shows)} bar/show subcategories covered")
    print("[selftest]", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--slug", help="Output slug -> data/osm_<slug>.csv")
    p.add_argument("--pbf", default=DEFAULT_PBF, help=f"Path to .osm.pbf (default: {DEFAULT_PBF})")
    p.add_argument("--bbox", help="Restrict to 'south,west,north,east' (same format as scrape_osm)")
    p.add_argument("--download", action="store_true", help="Fetch the national extract from Geofabrik")
    p.add_argument("--selftest", action="store_true", help="Verify tag->venue_type mapping offline")
    args = p.parse_args()

    if args.selftest:
        return _selftest()

    if args.download:
        rc = _download(args.pbf)
        if rc != 0 or not args.slug:
            return rc

    if not args.slug:
        p.error("--slug is required (or use --download / --selftest)")
    if not os.path.exists(args.pbf):
        p.error(f"{args.pbf} not found. Run with --download first.")

    rows = _parse(args.pbf, args.bbox)
    rows = _dedupe(rows)
    out = _write(rows, args.slug)
    print(f"[geofabrik] wrote {len(rows):,} rows -> {out}")

    from collections import Counter
    by_vt = Counter(r["venue_type"] or "(unset)" for r in rows)
    print("[geofabrik] venue_type breakdown:")
    for k, n in by_vt.most_common():
        print(f"  {n:>5}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
