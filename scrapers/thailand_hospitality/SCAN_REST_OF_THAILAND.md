# Scanning the rest of Thailand (hospitality — incl. bars & shows)

## Current coverage

| Tier | Count | Notes |
|------|-------|-------|
| Full (Wongnai + OSM) | 4 | Bangkok, Chiang Mai, Phuket, Udon Thani |
| OSM-only (no Wongnai restaurants/bars) | ~10 | Chiang Rai, Khon Kaen, Krabi, Korat, Surat Thani, Songkhla, Trang, Nan, Phitsanulok, Ranong |
| Has some data | ~42 slugs | per `data/hospitality_*.csv` |
| **Not yet scanned** | **39 provinces** | see `run_remaining_provinces.py --list` |

Wongnai bulk has only ever run for **5 of 77 provinces**. That gap is "the rest of Thailand".

## What changed for "bars & shows"

`scrape_osm.py` now also captures and tags each row with a `venue_type`:

- **bar** — `amenity=bar|pub|nightclub|stripclub`
- **show** — `amenity=theatre|cinema|arts_centre`, `leisure=stadium|dance|adult_gaming_centre`,
  `sport=muay_thai|boxing|martial_arts`, `tourism=theme_park` (cabaret, Muay Thai, theme-park shows)
- **lodging / attraction / spa** — as before

`venue_type` is threaded through `merge_hospitality.py` into `hospitality_<slug>.csv` and on into
`hospitality_country.csv` (filter with it for bar/show outreach lists). Wongnai bar/pub rows are
also tagged `bar`. `scrape_osm.py --place` geocodes any province via Nominatim, so no province
needs a hand-curated bbox.

## How to run (needs open network egress)

> ⚠️ Wongnai 403-bans aggressively and Overpass/Nominatim must be reachable. This must run from an
> environment whose network policy allows `wongnai.com`, `overpass-api.de`, and
> `nominatim.openstreetmap.org`. (The remote web session this was built in blocks them.)

```bash
cd scrapers/thailand_hospitality

python run_remaining_provinces.py --list          # preview the 39 remaining provinces
python run_remaining_provinces.py --limit 8       # one safe batch (~80-req Wongnai limit)
# ...repeat batches, or run all at once (long):
python run_remaining_provinces.py

# fold new provinces + bar/show venues into the country files + HTML report:
python aggregate_country.py
python finalize_country.py
```

Useful flags: `--skip-wongnai` (OSM bars+shows only, no 403 risk), `--max-pages N`,
`--wongnai-delay 15`, `--inter-city-delay 60`, `--include-done` (re-scan the OSM-only
provinces to add Wongnai bars + the new show categories).
