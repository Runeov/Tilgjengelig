# Thailand Cannabis Market Scraper

Two-tier snapshot of the Thai cannabis market for competitive-landscape research.
Pulls from two public directories with different verification standards:

| Source | Tier | Volume | Method |
|--------|------|--------|--------|
| [thaidispos.com](https://thaidispos.com) | Licensed (curated) | ~8 detail pages in sitemap (32 claimed) | Sitemap enumeration + per-page JSON-LD `Store` schema |
| [weed.th](https://weed.th) | Bulk-listed (unverified) | 11,271 unique shops | Single sitemap.xml fetch; city + name extracted from URL path |

## Regulatory context (read first)

Thailand reclassified cannabis as a controlled substance in **June 2025**. All purchases now require a **PT 33 medical prescription**. The gap between "licensed" (~8) and "listed" (~11K) reflects this transition — most weed.th entries pre-date the rule change and are likely closed, unlicensed, or in regulatory limbo. **This scraper does not verify current operating status.**

## Quick start

```powershell
# From project root. Dependencies (beautifulsoup4, requests, lxml) come from
# the project's existing requirements.txt and may already be installed.
pip install -r requirements.txt

# Run the full pipeline (each step writes a CSV into data/):
python scrapers/thailand_cannabis/scrape_thaidispos.py
python scrapers/thailand_cannabis/scrape_weed_th.py
python scrapers/thailand_cannabis/merge.py
python scrapers/thailand_cannabis/report.py

# Open the report:
start scrapers/thailand_cannabis/data/report.html
```

Total runtime: ~30 seconds (mostly the thaidispos detail-page fetches).

## Getting contact info per city (addresses + phone numbers)

The bulk pipeline above gives you names and cities only. To get **addresses, phones, websites, and hours per shop**, run the per-city enrichment in two stages:

```powershell
# Stage 1: extract addresses from weed.th detail pages (free, respects 1s crawl-delay)
python scrapers/thailand_cannabis/scrape_weed_th_detail.py --list-cities    # see what's available
python scrapers/thailand_cannabis/scrape_weed_th_detail.py "Udon Thani"     # ~5.5 min for 135 shops
# -> data/weed_th_udon_thani.csv with addresses + ratings (typically ~85% coverage)

# Stage 2: enrich with phone/website/hours from Google Places (requires API key, ~$0.03/shop)
$env:GOOGLE_MAPS_API_KEY = "AIza..."     # see "Google Places setup" below
python scrapers/thailand_cannabis/enrich_google_places.py data/weed_th_udon_thani.csv
# -> data/weed_th_udon_thani_google.csv with all original fields + google_phone, google_website, google_hours, etc.
```

**Honest limitation**: weed.th detail pages do **not** expose phone numbers, websites, or social handles. The only contact field on the page is the full street address (in JSON-LD). For phone numbers you must enrich via Google Places or another source.

### Google Places setup (one-time, ~5 min)

1. [Google Cloud Console](https://console.cloud.google.com/) -> create a project
2. APIs & Services -> Library -> enable **Places API (New)**
3. APIs & Services -> Credentials -> Create API Key (recommended: restrict it to "Places API (New)" only)
4. Billing -> link a billing account. Places API requires billing enabled, but Google's **$200/month free credit** covers ~6,500 contact lookups before any charge.
5. `$env:GOOGLE_MAPS_API_KEY = "AIza..."` in your PowerShell session

Cost for typical city scrapes: Udon Thani ~135 shops ≈ $4. Bangkok ~2,093 shops ≈ $63 (would consume one-third of the monthly free credit).

## Output files

All written to [data/](data/):

- `thaidispos.csv` — licensed dispensaries with full structured data (name, address, lat/lng, phone, website, rating, hours, price range)
- `weed_th.csv` — bulk listed shops (uuid, name, city, lastmod, detail URL)
- `weed_th_<city>.csv` — per-city detail scrape with full addresses + ratings (produced by `scrape_weed_th_detail.py`)
- `weed_th_<city>_google.csv` — above + phone/website/hours from Google Places (produced by `enrich_google_places.py`)
- `merged.csv` — union of the two bulk sources, with a `licensed` flag set where they cross-reference
- `matches.csv` — diagnostic table of the licensed↔listed matches with Jaccard scores
- `summary.json` — counts for downstream tools
- `report.html` — single-page HTML summary suitable for sharing

## Cross-reference matching

[merge.py](merge.py) cross-references the licensed tier against the listed tier using:

1. **City matching** — exact, with one carve-out: Koh Samui (island) is matched to Surat Thani (province) since weed.th uses the province.
2. **Name normalization** — lowercases, URL-decodes, strips common noise tokens (`cannabis`, `dispensary`, `shop`, `bangkok`, etc.) so "Wonderland Bangkok" and "wonderland-cannabis-bangkok" both reduce to "wonderland".
3. **Word-set Jaccard ≥ 0.4** — character-level fuzzy matching (`SequenceMatcher`) produced false positives like "stash rooftop" ↔ "high rooftop" (both share the word "rooftop" → 0.72 char similarity). Whole-token Jaccard rejects those cleanly. Character ratio is still recorded in `matches.csv` for diagnostics.

Current run: 7/8 licensed dispensaries found in weed.th. The unmatched one (Island Buds Koh Samui) is either absent or listed under a substantially different name.

## Honest limitations

- **thaidispos coverage is partial.** The site advertises 32 licensed dispensaries but only 8 appear in the sitemap. The Thai FDA's actual licensed count is larger; thaidispos is a curated subset, not the regulatory ground truth.
- **weed.th does not verify license status.** Many entries pre-date June 2025 and may be closed or operating unlawfully.
- **weed.th detail pages have no phone numbers, websites, or social links.** Verified by inspecting source HTML — only the address (in JSON-LD) and rating/reviews are exposed. For phone numbers you need Google Places enrichment or a different source.
- **No product or pricing data.** weed.th detail pages contain product menus with THC% and strain types, but pulling 11K detail pages at the required 1-second crawl-delay would take ~3 hours. Not pulled by default; if you need pricing, the cheap path is to fetch only the subset that cross-references a separate "currently licensed" list.
- **Google Places matching is heuristic.** The enrichment script picks the first Text Search result and tags confidence as high/medium/low based on whether the returned address mentions the input city. Low-confidence rows should be manually reviewed before action.
- **No data quality SLA.** Both sources are third-party. Validate any individual dispensary against the Thai FDA database before acting on it.

## Adding a third source

To add `cannabisforthailand.com` (the JS-rendered ~829-listing source), reuse the project's existing [browser_fetch.py](../../browser_fetch.py) Playwright integration. Pattern:

1. New file `scrape_cft.py` modeled on `scrape_thaidispos.py`.
2. Use `browser_fetch.fetch_with_browser(url, wait_for=...)` instead of `common.fetch(url)`.
3. Append its UUID-keyed records into `merge.py`'s existing cross-reference loop.

## File layout

```
scrapers/thailand_cannabis/
  __init__.py
  README.md              (this file)
  common.py                  (Dispensary dataclass, fetch, sitemap parser, normalization)
  scrape_thaidispos.py       (licensed tier — full structured data via JSON-LD)
  scrape_weed_th.py          (bulk universe — sitemap only, no detail fetches)
  scrape_weed_th_detail.py   (per-city: address + rating via JSON-LD, respects Crawl-delay)
  enrich_google_places.py    (per-city: + phone/website/hours via Google Places API)
  merge.py                   (cross-reference licensed vs listed tiers)
  report.py                  (HTML summary)
  data/                      (output, gitignored if you choose)
    thaidispos.csv
    weed_th.csv
    weed_th_<city>.csv
    weed_th_<city>_google.csv
    merged.csv
    matches.csv
    summary.json
    report.html
```
