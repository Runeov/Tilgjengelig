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

> ⚠️ This must run from an environment whose network policy allowlists the three data-source
> hosts. The default Claude Code web session blocks them (only pypi/github are allowed).

### Required allowlist hosts

| Host | Used for |
|------|----------|
| `overpass-api.de` | OSM bars & shows (the venue_type=show/bar venues) |
| `nominatim.openstreetmap.org` | province bounding boxes (`scrape_osm --place`) |
| `www.wongnai.com` | restaurants & bars (Wongnai bulk listings) |

To enable: start a **new Claude Code web session** with a network policy that allows these hosts
(custom allowlist or a more open policy — see
https://code.claude.com/docs/en/claude-code-on-the-web), or run on a machine with open network.

### Verify reachability, then scrape

```bash
cd scrapers/thailand_hospitality
pip install -r ../../requirements.txt      # beautifulsoup4, requests, lxml

python run_remaining_provinces.py --check         # preflight: confirms all 3 hosts reachable
python run_remaining_provinces.py --list          # preview the 39 remaining provinces
python run_remaining_provinces.py --limit 8       # one safe batch (~80-req Wongnai limit)
# ...repeat batches, or run all at once (long):
python run_remaining_provinces.py

# fold new provinces + bar/show venues into the country files + HTML report:
python aggregate_country.py
python finalize_country.py
```

The runner runs a network preflight automatically and aborts (exit 2) if any host is blocked, so
you never get an empty scrape. Use `--no-preflight` to bypass.

Useful flags: `--skip-wongnai` (OSM bars+shows only, no 403 risk), `--max-pages N`,
`--wongnai-delay 15`, `--inter-city-delay 60`, `--include-done` (re-scan the OSM-only
provinces to add Wongnai bars + the new show categories).
