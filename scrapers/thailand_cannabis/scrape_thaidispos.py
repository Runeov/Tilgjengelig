"""Scrape thaidispos.com — licensed Thai medical cannabis dispensary directory.

Enumeration: sitemap.xml lists each /dispensaries/{slug} URL.
Per-dispensary data: JSON-LD <script type="application/ld+json"> block of @type=Store
contains name, address, geo, telephone, openingHours, aggregateRating, etc.

Note: site claims 32 dispensaries but sitemap as of 2026-05 only lists 8 detail pages.
We scrape what is actually published.
"""

import os
import sys
from typing import Optional

# Allow running as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.thailand_cannabis.common import (  # noqa: E402
    DATA_DIR,
    DISPENSARY_FIELDS,
    Dispensary,
    dispensary_to_row,
    extract_jsonld,
    fetch,
    find_jsonld_by_type,
    iter_sitemap_urls,
    write_csv,
)

SITEMAP_URL = "https://thaidispos.com/sitemap.xml"
DETAIL_PREFIX = "https://thaidispos.com/dispensaries/"
# Per-request delay. Site has no Crawl-delay; we use a small courtesy delay.
REQUEST_DELAY = 0.5


def list_detail_urls() -> list[str]:
    """Fetch sitemap and return all dispensary detail URLs."""
    xml = fetch(SITEMAP_URL)
    return [
        u["loc"]
        for u in iter_sitemap_urls(xml)
        if u["loc"].startswith(DETAIL_PREFIX)
    ]


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def parse_detail(url: str, html: str) -> Optional[Dispensary]:
    """Parse a dispensary detail page into a Dispensary record."""
    blocks = extract_jsonld(html)
    store = find_jsonld_by_type(blocks, {"Store", "LocalBusiness", "Place"})
    if not store:
        return None

    address = store.get("address") or {}
    geo = store.get("geo") or {}
    rating = store.get("aggregateRating") or {}
    same_as = store.get("sameAs")
    website = None
    if isinstance(same_as, list) and same_as:
        website = same_as[0]
    elif isinstance(same_as, str):
        website = same_as

    slug = url.rsplit("/", 1)[-1]

    return Dispensary(
        source="thaidispos",
        source_id=slug,
        name=store.get("name", slug),
        city=address.get("addressLocality"),
        address=address.get("streetAddress"),
        latitude=_to_float(geo.get("latitude")),
        longitude=_to_float(geo.get("longitude")),
        phone=store.get("telephone"),
        website=website,
        rating=_to_float(rating.get("ratingValue")),
        review_count=_to_int(rating.get("reviewCount")),
        opening_hours=store.get("openingHours"),
        price_range=store.get("priceRange"),
        tags=[],
        licensed=True,  # thaidispos only lists licensed dispensaries
        detail_url=url,
    )


def scrape_all() -> list[Dispensary]:
    urls = list_detail_urls()
    print(f"[thaidispos] sitemap lists {len(urls)} detail URLs")
    results: list[Dispensary] = []
    for i, url in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] {url}")
        try:
            html = fetch(url, delay=REQUEST_DELAY if i > 1 else 0)
            d = parse_detail(url, html)
            if d:
                results.append(d)
            else:
                print(f"    ! no JSON-LD Store block found")
        except Exception as e:
            print(f"    ! error: {e}")
    return results


def main() -> int:
    results = scrape_all()
    out_path = os.path.join(DATA_DIR, "thaidispos.csv")
    write_csv(out_path, [dispensary_to_row(d) for d in results], DISPENSARY_FIELDS)
    print(f"\n[thaidispos] wrote {len(results)} dispensaries -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
