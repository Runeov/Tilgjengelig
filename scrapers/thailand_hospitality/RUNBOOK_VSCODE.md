# RUNBOOK — Scan the rest of Thailand from VS Code

Self-contained steps to run the hospitality scan (incl. **bars & shows**) on your own
machine in VS Code, then push the results. No Claude session required.

Everything below lives on branch **`claude/gracious-ride-CN6xL`**.

---

## 0. Prerequisites

- **Python 3.10+** and **git** installed.
- **Open internet** (home/office network is fine). The scan reaches:
  `overpass-api.de`, `nominatim.openstreetmap.org`, `www.wongnai.com`.
- This is the part that did NOT work inside the Claude web session — its network
  policy blocked those hosts. Running locally from VS Code avoids that entirely.

---

## 1. Get the code in VS Code

Open VS Code → Terminal (`Ctrl+`` ` ``) and run:

```bash
# if you don't have the repo yet:
git clone https://github.com/Runeov/Tilgjengelig.git
cd Tilgjengelig

# get the scan branch:
git fetch origin claude/gracious-ride-CN6xL
git checkout claude/gracious-ride-CN6xL
git pull origin claude/gracious-ride-CN6xL
```

---

## 2. Install dependencies

```bash
cd scrapers/thailand_hospitality
python -m pip install -r ../../requirements.txt    # beautifulsoup4, requests, lxml
```

(Optional but recommended: use a virtualenv first —
`python -m venv .venv && source .venv/bin/activate` on macOS/Linux, or
`.venv\Scripts\activate` on Windows.)

---

## 3. Confirm the data sources are reachable

```bash
python run_remaining_provinces.py --check
```

You want three `OK` lines. If any say `BLOCKED`, your network is blocking that host —
switch networks / disable a VPN / firewall and retry. **Do not proceed until all 3 are OK.**

Preview what will be scanned:

```bash
python run_remaining_provinces.py --list      # ~39 remaining provinces
```

---

## 4. Run the scan

### Recommended: fast OSM-only first pass (bars + shows, zero ban risk)

OpenStreetMap has no rate-ban risk, so grab all the **bars & shows** first:

```bash
SKIP_WONGNAI=1 ./scan_rest_of_thailand.sh
```

On Windows (PowerShell), set the var separately:

```powershell
$env:SKIP_WONGNAI=1 ; bash scan_rest_of_thailand.sh
```

### Full run (adds Wongnai restaurants & bars)

```bash
./scan_rest_of_thailand.sh
```

This: preflight → scrapes each remaining province (Wongnai + OSM + merge) in up to
3 resume passes → aggregates country-wide files → **auto-commits** the results.

**Resume-safe:** press `Ctrl+C` anytime and re-run — finished provinces are skipped.

### Tuning (env vars)

| Var | Default | Meaning |
|-----|---------|---------|
| `MAX_PAGES` | 50 | Wongnai pages/province (~20 shops/page) |
| `WONGNAI_DELAY` | 15 | seconds between Wongnai fetches — **raise to 20–30 if you get 403s** |
| `INTER_CITY_DELAY` | 60 | cool-off between provinces |
| `PASSES` | 3 | resume retry passes |
| `LIMIT` | (all) | only the next N provinces, e.g. `LIMIT=8` for one batch |
| `SKIP_WONGNAI` | (off) | OSM bars+shows only |
| `NO_COMMIT` | (off) | don't auto-commit |

Example one safe batch with a gentler Wongnai rate:

```bash
LIMIT=8 WONGNAI_DELAY=25 ./scan_rest_of_thailand.sh
```

---

## 5. What you get (in `data/`)

| File | Contents |
|------|----------|
| `hospitality_country.csv` | all unique businesses, with a **`venue_type`** column |
| `reachable_country_final.csv` | the contactable subset (phone/email/URL) |
| `contact_list_country.csv` | slim outreach-ready list |
| `report_hospitality_country.html` | top-prospects HTML report (open in browser) |
| `hospitality_<province>.csv` | one per scanned province |

`venue_type` values: **`bar`**, **`show`**, `lodging`, `attraction`, `spa`.

### Pull out just bars / shows

```bash
# bars
awk -F, 'NR==1 || $0 ~ /,bar,/'  data/hospitality_country.csv > bars_country.csv
# shows (cabaret, theatre, Muay Thai, theme-park shows)
awk -F, 'NR==1 || $0 ~ /,show,/' data/hospitality_country.csv > shows_country.csv
```

(Or just open `hospitality_country.csv` in VS Code / Excel and filter the `venue_type` column.)

---

## 6. Push the results

The script auto-commits on success. Push it:

```bash
git push -u origin claude/gracious-ride-CN6xL
```

If you used `NO_COMMIT=1`, commit manually first:

```bash
git add scrapers/thailand_hospitality/data/
git commit -m "Add scanned hospitality data for rest of Thailand (bars & shows)"
git push -u origin claude/gracious-ride-CN6xL
```

---

## 7. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `--check` shows BLOCKED | Network/VPN/firewall blocking the host; switch network and retry. |
| Wongnai `403` mid-run | You hit the IP rate limit. Re-run with `WONGNAI_DELAY=30`; it resumes and skips done provinces. Wait ~10 min if banned. |
| `requests` not found | `python -m pip install -r ../../requirements.txt` |
| Overpass timeout on a big province | Re-run; it's transient. The query has a 120s server timeout. |
| Want to re-scan an OSM-only province (Chiang Rai, Khon Kaen, etc.) to add bars/Wongnai | `python run_remaining_provinces.py --include-done --limit 1` after deleting its `hospitality_<slug>.csv`, or scrape that slug directly. |
| Script won't run on Windows | Use Git Bash / WSL: `bash scan_rest_of_thailand.sh`. |

---

## Alternative data paths (also on this branch)

Parallel work added more sources beyond the live Overpass+Wongnai pipeline. See
`DATA_SOURCES.md` for the full catalogue. The most useful:

### A. Geofabrik bulk-OSM — **best for whole-country bars & shows, no rate limit**

One national download, parsed offline — covers all 77 provinces, zero Overpass/403 risk.
Only needs egress to `download.geofabrik.de` (once).

```bash
pip install pyrosm                              # parses .osm.pbf
python scrape_geofabrik.py --selftest           # verify logic, no network/deps needed
python scrape_geofabrik.py --download           # download Thailand extract once
python scrape_geofabrik.py --slug rayong --bbox 12.5,101.0,13.2,101.9   # per-province file
# ...repeat per province (bboxes via Nominatim or scrape_osm KNOWN_BBOXES), then:
python aggregate_country.py && python finalize_country.py
```

Output is a byte-compatible `data/osm_<slug>.csv` the merge pipeline already consumes.
(pyrosm's tag layout should be confirmed on the first real run — see the note in the script.)

### B. Event/booking platforms

```bash
python scrape_ticketmelon.py   # live SHOWS: concerts, Muay Thai, cabaret (strongest show source)
python scrape_eatigo.py        # restaurants & bars (reservation platform, contactable subset)
```

### C. Manual dataset — usable right now, no network

`data/search_bars_shows_thailand.csv` — 65 hand-compiled venues (54 bars + 11 shows, 7 provinces).
Listicle-derived and partial (no coords/phone/website), but a ready quick-start outreach list.

---

## Reference — what was built

- `scrape_osm.py` — captures bars (`bar/pub/nightclub/stripclub`) + shows
  (`theatre/cinema/arts_centre`, `stadium/dance`, `muay_thai/boxing`, `theme_park`),
  tags each row `venue_type`, geocodes any province via `--place` (Nominatim).
- `scrape_wongnai.py` — `--out-slug` for clean filenames when passing a province by name.
- `merge_hospitality.py` — scores bars/shows as tourism-relevant; threads `venue_type` through.
- `run_remaining_provinces.py` — picks the not-yet-covered provinces; `--check`, `--list`, `--limit`.
- `scan_rest_of_thailand.sh` — the one-shot wrapper (preflight → scrape → aggregate → commit).

See `SCAN_REST_OF_THAILAND.md` for the coverage map and design notes.
