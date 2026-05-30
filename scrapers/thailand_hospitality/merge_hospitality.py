"""Merge Wongnai food + OSM lodging/attractions/nightlife + FB ads signal
into one deduped hospitality dataset with a B2B lead-quality score.

Dedup logic: a Wongnai bar/pub and an OSM bar/pub are the SAME business if
their normalized names share enough word overlap (Jaccard >= 0.4) AND they
are within ~250m of each other (geo distance via simple lat/lng degrees).

Score (raw 0-13, normalized 0-10):
  +3  has a real-domain website (NOT facebook/instagram/line/linktree)
  +3  has FB ads with count in [1, 100] (clean signal)
  +1  has FB ads with count > 100 (ambiguous — generic-name false positive risk)
  +2  in tourism-relevant category (bar / nightclub / cafe / hotel / attraction)
  +2  has phone (any source)
  +1  has email (any source)
  +up to 3 from log10(review_count + 1) when review data is available

Output: data/hospitality_<city>.csv with one row per unique business + score.

Usage:
  python merge_hospitality.py udonthani
"""

import argparse
import csv
import math
import os
import re
import sys
from collections import defaultdict
from typing import Optional
from urllib.parse import urlparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

# Categories that indicate tourist-relevant business (bias the scoring).
TOURISM_CATEGORIES_WONGNAI = {
    "กึ่งผับ/ร้านเหล้า/บาร์", "คาเฟ่", "ร้านกาแฟ/ชา",
    "อาหารฝรั่งเศส", "อาหารอิตาเลียน", "อาหารญี่ปุ่น",
    "อาหารเกาหลี", "อาหารตะวันตก", "อาหารนานาชาติ",
    "อาหารเวียดนาม", "พิซซ่า", "เบอร์เกอร์", "สเต็ก",
    "ชาบู/สุกี้ยากี้/หม้อไฟ", "อาหารทะเล",
}
TOURISM_SUBCATEGORIES_OSM = {
    # Lodging
    "hotel", "guest_house", "hostel", "motel", "apartment", "resort",
    # Attractions
    "attraction", "viewpoint", "museum", "gallery", "theme_park",
    # Nightlife
    "bar", "pub", "nightclub", "spa",
    # Food & drink (added — user's primary B2B target)
    "restaurant", "cafe", "fast_food", "food_court", "biergarten", "ice_cream",
}

# URL hosts that are NOT real websites (social-only presence)
SOCIAL_HOSTS = {
    "facebook.com", "m.facebook.com", "fb.me",
    "instagram.com", "instagr.am",
    "line.me", "lin.ee", "linktr.ee", "beacons.ai", "bio.link",
    "heylink.me", "taplink.cc", "url.in.th",
    "tiktok.com", "twitter.com", "x.com", "youtube.com", "youtu.be",
    "t.me",
}

# Normalization (reused pattern from cannabis project)
_NAME_NOISE = re.compile(
    r"\b(restaurant|cafe|cafeteria|bar|pub|club|hotel|resort|"
    r"udon\s*thani|udon|thani|thailand|the|and|&|"
    r"ร้าน|ร้านอาหาร|คาเฟ่|บาร์|ผับ|โรงแรม|รีสอร์ท|"
    r"อุดรธานี|อุดร|ธานี)\b",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9฀-๿]+")


def normalize_name(name: str) -> str:
    if not name:
        return ""
    s = name.lower().strip()
    s = _NAME_NOISE.sub(" ", s)
    s = _NON_ALNUM.sub(" ", s)
    return " ".join(s.split())


def word_jaccard(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def geo_distance_km(a_lat, a_lng, b_lat, b_lng) -> float:
    """Rough km distance using equirectangular approximation. Good enough for dedup."""
    try:
        a_lat, a_lng = float(a_lat), float(a_lng)
        b_lat, b_lng = float(b_lat), float(b_lng)
    except (TypeError, ValueError):
        return 9999.0
    avg_lat_rad = math.radians((a_lat + b_lat) / 2)
    x = (b_lng - a_lng) * math.cos(avg_lat_rad)
    y = b_lat - a_lat
    return math.sqrt(x * x + y * y) * 111.0  # 111 km per degree latitude


def is_real_website(url: str) -> bool:
    if not url or not url.startswith(("http://", "https://")):
        return False
    try:
        host = (urlparse(url).hostname or "").lower().lstrip(".")
    except Exception:
        return False
    if host.startswith("www."):
        host = host[4:]
    return bool(host) and host not in SOCIAL_HOSTS


def load_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_unified_rows(slug: str) -> list[dict]:
    """Read Wongnai + Wongnai-detailed + OSM + FB ads CSVs and build unified row dicts."""
    rows: list[dict] = []

    # 1a. Wongnai detail enrichment (if exists) — keyed by publicId
    detailed = load_csv(os.path.join(DATA_DIR, f"wongnai_{slug}_detailed.csv"))
    det_by_pid = {r.get("publicId"): r for r in detailed if r.get("publicId")}

    # 1b. Wongnai food/drink bulk
    wongnai = load_csv(os.path.join(DATA_DIR, f"wongnai_{slug}.csv"))
    for r in wongnai:
        pid = r.get("publicId", "")
        d = det_by_pid.get(pid, {})
        rows.append({
            "src_id": f"wongnai:{pid}",
            "sources": "wongnai",
            "name": r.get("displayName", ""),
            "name_thai": r.get("name_thai", ""),
            "name_en": r.get("name_english", ""),
            "category_raw": r.get("primary_category", ""),
            "subcategory": r.get("primary_category", ""),
            "is_food": r.get("is_likely_food") == "1",
            "lat": r.get("lat", ""),
            "lng": r.get("lng", ""),
            "zipcode": r.get("zipcode", ""),
            "address": d.get("address_street", ""),           # from detail page
            "phone": d.get("telephone", ""),                   # from detail page
            "website": "",
            "email": "",
            "detail_url": r.get("detail_url", ""),
            "wongnai_categories": r.get("categories", ""),
            "wongnai_cuisine": d.get("serves_cuisine", ""),
            "wongnai_price_range": d.get("price_range", ""),
            "wongnai_opening_hours": d.get("opening_hours_summary", ""),
            "wongnai_rating": d.get("rating", ""),
            "wongnai_review_count": d.get("review_count", ""),
        })

    # 2. OSM hotels/bars/attractions
    osm = load_csv(os.path.join(DATA_DIR, f"osm_{slug}.csv"))
    for r in osm:
        rows.append({
            "src_id": f"osm:{r.get('osm_id', '')}",
            "sources": "osm",
            "name": r.get("name", ""),
            "name_thai": r.get("name_th", ""),
            "name_en": r.get("name_en", ""),
            "category_raw": r.get("subcategory", ""),
            "subcategory": r.get("subcategory", ""),
            "is_food": r.get("subcategory") in ("restaurant", "cafe", "bar", "pub", "fast_food"),
            "lat": r.get("lat", ""),
            "lng": r.get("lng", ""),
            "zipcode": "",
            "address": r.get("address_full", ""),
            "phone": r.get("phone", ""),
            "website": r.get("website", ""),
            "email": r.get("email", ""),
            "detail_url": "",
            "osm_subcategory": r.get("subcategory", ""),
        })

    # 3. FB ads — keyed by Wongnai publicId
    fb_ads = load_csv(os.path.join(DATA_DIR, f"fb_ads_{slug}.csv"))
    fb_by_pid = {r.get("publicId"): r for r in fb_ads if r.get("publicId")}
    for row in rows:
        if row["src_id"].startswith("wongnai:"):
            pid = row["src_id"].split(":", 1)[1]
            fb = fb_by_pid.get(pid)
            if fb:
                row["fb_ad_count"] = fb.get("fb_ad_count", "")
                row["fb_search_url"] = fb.get("fb_search_url", "")
                row["fb_check_status"] = fb.get("fb_check_status", "")
            else:
                row["fb_ad_count"] = ""
                row["fb_search_url"] = ""
                row["fb_check_status"] = ""
        else:
            row["fb_ad_count"] = ""
            row["fb_search_url"] = ""
            row["fb_check_status"] = ""

    return rows


def dedup(rows: list[dict], distance_km: float = 0.25, jaccard_threshold: float = 0.4) -> list[dict]:
    """Merge wongnai+osm rows that are likely the same business.
    Conservative: only merge across sources, never within the same source."""
    # Bucket OSM rows by zip-rounded geo cell for quick lookup
    osm_rows = [r for r in rows if r["sources"] == "osm"]
    wongnai_rows = [r for r in rows if r["sources"] == "wongnai"]
    used_osm_ids: set = set()
    merged: list[dict] = []

    for w in wongnai_rows:
        wname = normalize_name(w["name"])
        best = None
        best_score = 0.0
        if wname:
            for o in osm_rows:
                if o["src_id"] in used_osm_ids:
                    continue
                d = geo_distance_km(w["lat"], w["lng"], o["lat"], o["lng"])
                if d > distance_km:
                    continue
                j = word_jaccard(wname, normalize_name(o["name"]))
                if j >= jaccard_threshold and j > best_score:
                    best, best_score = o, j
        if best:
            used_osm_ids.add(best["src_id"])
            # Merge: prefer existing wongnai fields, fill from OSM
            mergedrow = dict(w)
            mergedrow["sources"] = "wongnai+osm"
            mergedrow["src_id_alt"] = best["src_id"]
            for k in ("address", "phone", "website", "email"):
                if not mergedrow.get(k) and best.get(k):
                    mergedrow[k] = best[k]
            if not mergedrow.get("osm_subcategory"):
                mergedrow["osm_subcategory"] = best.get("osm_subcategory", "")
            merged.append(mergedrow)
        else:
            merged.append(w)

    # Append OSM rows that didn't merge
    for o in osm_rows:
        if o["src_id"] in used_osm_ids:
            continue
        merged.append(o)

    return merged


def is_tourism(row: dict) -> bool:
    if row.get("category_raw") in TOURISM_CATEGORIES_WONGNAI:
        return True
    if row.get("osm_subcategory") in TOURISM_SUBCATEGORIES_OSM:
        return True
    if row.get("subcategory") in TOURISM_SUBCATEGORIES_OSM:
        return True
    return False


def compute_score(row: dict) -> tuple[int, str, str]:
    """Return (raw_score, normalized_0_10, score_factors_text)."""
    raw = 0
    factors = []

    if is_real_website(row.get("website") or ""):
        raw += 3
        factors.append("+3 real website")

    try:
        fb_n = int(row.get("fb_ad_count") or 0)
    except ValueError:
        fb_n = 0
    if 1 <= fb_n <= 100:
        raw += 3
        factors.append(f"+3 FB ads ({fb_n})")
    elif fb_n > 100:
        raw += 1
        factors.append(f"+1 FB ads ambig ({fb_n}, likely false-pos)")

    if is_tourism(row):
        raw += 2
        factors.append("+2 tourism category")

    if (row.get("phone") or "").strip():
        raw += 2
        factors.append("+2 phone")
    if (row.get("email") or "").strip():
        raw += 1
        factors.append("+1 email")

    # Review count (when available, from Wongnai detail page OR Google Places enrichment)
    try:
        rc = int(row.get("review_count") or row.get("google_user_ratings")
                 or row.get("wongnai_review_count") or 0)
    except (ValueError, TypeError):
        rc = 0
    if rc > 0:
        rev_bonus = min(3, int(math.log10(rc + 1)))
        if rev_bonus:
            raw += rev_bonus
            factors.append(f"+{rev_bonus} reviews ({rc})")

    quality = min(10, round(raw * 10 / 14))
    return raw, str(quality), " ; ".join(factors)


CSV_FIELDS = [
    "src_id", "src_id_alt", "sources",
    "name", "name_thai", "name_en",
    "category_raw", "subcategory", "is_food",
    "lat", "lng", "zipcode", "address",
    "phone", "website", "email",
    "wongnai_categories", "osm_subcategory",
    "wongnai_cuisine", "wongnai_price_range", "wongnai_opening_hours",
    "wongnai_rating", "wongnai_review_count",
    "fb_ad_count", "fb_check_status", "fb_search_url",
    "review_count",
    "is_tourism", "lead_raw", "lead_quality", "score_factors",
    "detail_url",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slug", help="City slug (e.g. 'udonthani')")
    args = parser.parse_args()

    print(f"[merge] loading data for {args.slug}...")
    raw_rows = build_unified_rows(args.slug)
    n_wongnai = sum(1 for r in raw_rows if r["sources"] == "wongnai")
    n_osm = sum(1 for r in raw_rows if r["sources"] == "osm")
    print(f"[merge] before dedup: {n_wongnai} wongnai + {n_osm} osm = {len(raw_rows)} rows")

    merged = dedup(raw_rows)
    n_merged_both = sum(1 for r in merged if r["sources"] == "wongnai+osm")
    n_wongnai_only = sum(1 for r in merged if r["sources"] == "wongnai")
    n_osm_only = sum(1 for r in merged if r["sources"] == "osm")
    print(f"[merge] after dedup: {len(merged)} unique businesses")
    print(f"[merge]   wongnai-only: {n_wongnai_only}")
    print(f"[merge]   osm-only:     {n_osm_only}")
    print(f"[merge]   both sources: {n_merged_both}")

    # Score every row
    for r in merged:
        raw, qual, factors = compute_score(r)
        r["lead_raw"] = str(raw)
        r["lead_quality"] = qual
        r["score_factors"] = factors
        r["is_tourism"] = "1" if is_tourism(r) else "0"
        r["review_count"] = r.get("review_count", "")
        r["src_id_alt"] = r.get("src_id_alt", "")

    # Sort by score desc
    merged.sort(key=lambda r: -int(r.get("lead_raw") or 0))

    out_path = os.path.join(DATA_DIR, f"hospitality_{args.slug}.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in merged:
            writer.writerow({k: r.get(k, "") for k in CSV_FIELDS})
    print(f"[merge] wrote {out_path}")

    # Score distribution
    from collections import Counter
    qs = Counter(r["lead_quality"] for r in merged)
    print(f"\n[merge] score distribution:")
    for q in sorted(qs.keys(), key=lambda x: -int(x)):
        print(f"  quality={q}: {qs[q]}")

    tourism_only = [r for r in merged if r["is_tourism"] == "1"]
    print(f"\n[merge] tourism-relevant (bar/cafe/hotel/etc): {len(tourism_only)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
