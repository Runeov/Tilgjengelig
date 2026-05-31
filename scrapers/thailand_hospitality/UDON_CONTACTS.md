# Udon Thani bars & shows — contact enrichment

Manual web-search enrichment of bar/show venues that were missing **all** contact
info (no phone/website/email) in `hospitality_udonthani.csv`.

## Result

- **`data/udon_barshow_contacts.csv`** — 30 venues enriched
  - 17 with phone, 28 with Facebook, 4 with email, 3 with website
  - columns: `name, phone, email, website, facebook, address, note, source`
- **`data/_udon_barshow_misses.txt`** — 30 names searched with no findable Udon
  contact (tiny local/girly bars, or venues actually in Vientiane, Laos)
- **`data/_udon_barshow_worklist_clean.json`** — the 95 cleaned candidates
  (after dropping ~14 Lao-script venues + 6 government-building false-positives
  from the original 129 heuristic matches)

## Method & provenance

Source data hosts (Overpass/Wongnai) and WebFetch were all egress-blocked, so
this used **manual WebSearch** only, reading result summaries for phone / address
/ Facebook / email. Each row's `source` column records this. Data is
search-summary-derived — **verify before outreach** (a few venues were flagged
permanently closed, e.g. Nuchy Music Bar).

## What got captured vs. left

**Captured (high-yield):** expat bars (Irish Clock, Pegasus, Full Throttle,
Vikings Corner, Fun Bar, Honey Bar 1, Red Lion, Zur Pfalz, Smile Bar…), major
nightspots (Tawandang, The Library, UD Town, Country Bar), chain cinemas (Major,
SF, EGV), plus bonus finds not in the worklist (Rhythm & Bar, FIX Club, Lucky
Bar, Night Club Phoenix).

**Left (deliberately, low ROI):** ~50 long-tail names — generic single-word local
bars and a cluster of Vientiane/Laos venues that shouldn't be in the Udon dataset
at all. Per-venue search yield on these had dropped to ~15%. Best handled by a
**networked scraper run** (Geofabrik/OSM + Wongnai detail pages) that pulls
contacts in bulk, rather than more manual searching.

## To resume / fold back in

1. The clean worklist still holds the unprocessed names; subtract those already in
   `udon_barshow_contacts.csv` and `_udon_barshow_misses.txt`.
2. To merge these contacts back into `hospitality_udonthani.csv`, match on `name`
   (most are exact) and fill empty `phone`/`website`/`email` — keep a `source`
   marker so search-derived values are distinguishable from scraped ones.
