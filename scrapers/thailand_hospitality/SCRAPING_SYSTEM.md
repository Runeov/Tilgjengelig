# City contact-scraping system (repeatable playbook)

The proven, repeatable way we build a contactable venue directory for a city and
load it into KrobJob. Built and validated on **Udon Thani**; designed so each new
city is faster than the last.

## The pipeline

```
OSM/Wongnai scrape ──► hospitality_<slug>.csv      (the raw directory: every company)
        │
        ▼
manual web-search harvest ──► contacts_<slug>.csv  (phone/email/website/facebook/address)
   (enrich_city.add + method log)
        │
        ▼
krobjob seed-city <slug> ──► SQLite directory       (prospects, contactable, social)
        │
        ▼
enrich_facebook.py ──► fills phones from FB pages   (network-enabled session)
        │
        ▼
promote → comms/contracts → sales/expenses → agent reports
```

## Step 1 — raw directory (per city)

Scrape OSM + Wongnai into `data/hospitality_<slug>.csv` (see `scrape_osm.py`,
`scrape_geofabrik.py`, `scrape_wongnai.py`, `run_remaining_provinces.py`). This is
"every company listed". Needs network egress to the data hosts.

## Step 2 — contact harvest (the proven method)

For venues missing contact info, run web searches and record results via the
reusable engine. **Proven query templates** (ranked by Udon yield) live in
`enrich_city.QUERY_TEMPLATES`; **proven source domains** in `PROVEN_SOURCES`.

```python
import enrich_city
enrich_city.add("rayong", [
  {"name": "Some Bar", "venue_type": "bar", "phone": "+66 ...",
   "facebook": "https://facebook.com/...", "address": "...",
   "query": "Some Bar Rayong phone address facebook"},
], city="Rayong", province="Rayong")
```

`add()` dedupes by name, fills blanks on merge, and logs every attempt to
`_enrichment_log.csv` (hit / partial / miss, which fields, the query). Review what
works with:

```bash
python enrich_city.py proven        # hit-rate + phone-rate, overall and per city
python enrich_city.py stats <slug>
```

**Lesson from Udon (drives the next city):**
- Best yield: established/expat venues + chain venues (cinemas, malls) → ~90% have
  phone+Facebook. The long tail of tiny local bars and cross-border (Vientiane)
  venues → ~15%; don't over-invest there.
- Facebook is almost always findable even when phone isn't → capture it, then use
  `enrich_facebook.py` to backfill phones.
- Search summaries from facebook.com, restaurantguru, tripadvisor, wanderlog,
  ilovit, udon-map, trip.com carry the contact line most often.

## Step 3 — load into KrobJob (one call per city)

```bash
python -m krobjob seed-city <slug> --province "<Province>"
```

Imports `hospitality_<slug>.csv` as prospects, derives `venue_type`, and overlays
`contacts_<slug>.csv` (inserting enriched venues that weren't in the raw scrape).

## Step 4 — Facebook phone backfill (network session)

```bash
python enrich_facebook.py --check          # confirm facebook.com reachable
python enrich_facebook.py                  # pull phones for FB-only venues
python enrich_facebook.py --merge          # fold reviewed phones into contacts
```

This also primes the **Facebook outreach** channel: once an FB account is
connected, the same pages feed `krobjob comm log <venue> --channel facebook ...`.

## Onboarding a new city — checklist

1. `scrape_*` → `data/hospitality_<slug>.csv`
2. Harvest contacts with `enrich_city.add(...)` using `QUERY_TEMPLATES`
3. `python enrich_city.py proven` to confirm method effectiveness
4. `python -m krobjob seed-city <slug> --province "<Province>"`
5. `enrich_facebook.py` in a network session
6. `python -m krobjob trends --province "<Province>"` for the market view

## Files

| File | Role |
|------|------|
| `enrich_city.py` | reusable harvest engine: schema, dedupe/merge, method log, proven report |
| `data/contacts_<slug>.csv` | per-city contacts (standard schema) |
| `data/_enrichment_log.csv` | every attempt — the "proven ways" data |
| `enrich_facebook.py` | phone backfill from Facebook pages |
| `krobjob seed-city` | one-call city → CRM directory |
