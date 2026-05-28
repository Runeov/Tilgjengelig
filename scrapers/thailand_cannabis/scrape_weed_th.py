"""Scrape weed.th — the bulk-listed cannabis shop universe in Thailand.

weed.th's sitemap.xml exposes every shop as
  https://weed.th/shop/{uuid}/{city-slug}/{name-slug}[?locale=th]
plus a Thai-locale duplicate. We dedupe by uuid, extract city + name directly
from the URL path, and use sitemap <lastmod> as a freshness signal.

This is the LISTED universe — many of these shops are likely closed or
unlicensed after the June 2025 Thai medical-only reclassification. See merge.py
for cross-reference against thaidispos (the licensed tier).

No per-shop fetches: a single sitemap request yields the full dataset.
robots.txt declares Crawl-delay: 1 — we honor it but only need one request anyway.
"""

import os
import re
import sys
from typing import Optional
from urllib.parse import unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.thailand_cannabis.common import (  # noqa: E402
    DATA_DIR,
    DISPENSARY_FIELDS,
    Dispensary,
    dispensary_to_row,
    fetch,
    iter_sitemap_urls,
    write_csv,
)

SITEMAP_URL = "https://weed.th/sitemap.xml"
SHOP_PREFIX = "https://weed.th/shop/"
TH_SHOP_PREFIX = "https://weed.th/th/shop/"

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def parse_shop_url(url: str) -> Optional[Dispensary]:
    """Parse a weed.th shop URL into a Dispensary record. Returns None if not a shop URL."""
    parsed = urlparse(url)
    if parsed.netloc != "weed.th":
        return None
    parts = [p for p in parsed.path.split("/") if p]
    # Expect: ["shop", uuid, city, name]  (English locale)
    # or:     ["th", "shop", uuid, city, name]  (Thai locale — skipped as dupe)
    if parts and parts[0] == "th":
        return None
    if len(parts) < 4 or parts[0] != "shop":
        return None
    uuid, city_slug, name_slug = parts[1], parts[2], parts[3]
    if not _UUID_RE.match(uuid):
        return None

    name = unquote(name_slug).replace("-", " ").strip()
    city = unquote(city_slug).replace("-", " ").strip().title()

    return Dispensary(
        source="weed_th",
        source_id=uuid,
        name=name,
        city=city,
        licensed=None,  # unknown — weed.th does not verify license status
        detail_url=url,
    )


def scrape_all() -> list[Dispensary]:
    print(f"[weed.th] fetching sitemap: {SITEMAP_URL}")
    xml = fetch(SITEMAP_URL)
    print(f"[weed.th] sitemap size: {len(xml):,} bytes")

    seen_uuids: set[str] = set()
    results: list[Dispensary] = []
    skipped_th_locale = 0
    skipped_query_locale = 0
    skipped_other = 0

    for entry in iter_sitemap_urls(xml):
        loc = entry["loc"]
        # Skip Thai-locale duplicates (?locale=th query param)
        if "?locale=th" in loc:
            skipped_query_locale += 1
            continue
        if loc.startswith(TH_SHOP_PREFIX):
            skipped_th_locale += 1
            continue
        if not loc.startswith(SHOP_PREFIX):
            skipped_other += 1
            continue
        d = parse_shop_url(loc)
        if not d:
            continue
        if d.source_id in seen_uuids:
            continue
        seen_uuids.add(d.source_id)
        d.lastmod = entry.get("lastmod")
        results.append(d)

    print(f"[weed.th] skipped: {skipped_th_locale} /th/ duplicates, "
          f"{skipped_query_locale} ?locale=th duplicates, {skipped_other} non-shop URLs")
    print(f"[weed.th] unique shops: {len(results):,}")
    return results


def main() -> int:
    results = scrape_all()
    out_path = os.path.join(DATA_DIR, "weed_th.csv")
    write_csv(out_path, [dispensary_to_row(d) for d in results], DISPENSARY_FIELDS)
    print(f"\n[weed.th] wrote {len(results):,} shops -> {out_path}")

    # Quick city distribution to sanity-check
    from collections import Counter
    by_city = Counter(d.city for d in results)
    print("\n[weed.th] top 15 cities:")
    for city, n in by_city.most_common(15):
        print(f"  {n:5d}  {city}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
