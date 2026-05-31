# WORKLOG — KrobJob / Thailand hospitality

Handoff record for moving to cowork. Branch: `claude/gracious-ride-CN6xL` (PR #1).
Scope: build a contactable company directory for Thailand hospitality, a CRM +
recommendation system (KrobJob) on top of it, and a repeatable per-city pipeline.

## Current state (snapshot)

| Area | State |
|------|-------|
| **KrobJob CRM** | `krobjob/` package, SQLite + CLI. Directory **3,706 companies** (Udon Thani), 546 contactable, 76 with social. Pipeline: prospect→client, comms, contracts, sales/expenses, agent reports. Built & tested **offline**. |
| **Udon contacts** | `contacts_udonthani.csv` — **83 venues**, 44 phone, 76 facebook, 13 email, 8 website, 83 address. `_udon_barshow_misses.txt` — 36 searched-but-unfindable. |
| **Scraping system** | `enrich_city.py` (reusable harvest engine + method log), `enrich_facebook.py` (FB phone backfill), `scrape_osm/geofabrik/wongnai/ticketmelon/eatigo.py`. |
| **Method log** | `_enrichment_log.csv` — 83 attempts, **53% phone hit-rate, 47% partial**. |
| **Reports / playbook** | `SCRAPING_SYSTEM.md`, `DATA_SOURCES.md`, `SCAN_REST_OF_THAILAND.md`, `krobjob/README.md`, `UDON_CONTACTS.md`. |
| **Commits on branch** | 27 (since `master`). |

## What was done, in order

1. **Scraping infra (pre-existing + extended).** OSM/Wongnai scrapers and the
   "rest of Thailand" runner. Added `scrape_geofabrik.py` (bulk OSM, no rate
   limit), `scrape_ticketmelon.py` (shows), `scrape_eatigo.py` (restaurants/bars)
   — JSON-first, each with an offline `--selftest`. Catalogued sources in
   `DATA_SOURCES.md`.
2. **Manual contact harvest (Udon Thani).** Because live egress was blocked
   (see ERROR_LOG), enriched venues via WebSearch result summaries. Grew from a
   129-name worklist (mostly unfindable tail) to a broad nightlife + restaurant
   harvest: **31 → 83 venues** with contacts.
3. **KrobJob CRM.** SQLite schema (companies, clients, social_profiles,
   communications, contracts, sales, expenses, reports); CLI (`python -m
   krobjob`); recommendation `agent.py` (offline heuristics + optional Claude
   hook); HTML `report.py`. Seeded from the Udon hospitality directory + the
   enriched contacts. Verified end-to-end offline (promote client, log
   sales/expenses, generate performance + market-trend reports).
4. **Repeatable system.** Generalised to any city: `enrich_city.py` engine
   (standard schema, dedupe/merge, method log, proven-ways report) and
   `krobjob seed-city <slug> --province` one-call onboarding. Documented the
   end-to-end playbook in `SCRAPING_SYSTEM.md`.
5. **Facebook readiness.** `enrich_facebook.py` (pull phones from FB pages) +
   KrobJob `--channel facebook` comms for outreach, pending a connected account
   and network egress.

## Key lessons (drive the next city)

- High-presence venues (expat bars, chains, cinemas, malls) ≈ **90% yield**;
  tiny local + cross-border (Vientiane) tail ≈ **15%** — don't over-invest there.
- Facebook is findable even when phone isn't → capture FB, backfill phones with
  `enrich_facebook.py`.
- Always record through `enrich_city.add()` so the method log accrues the
  "proven ways" data for the next city.

## Open / next

- **Network-enabled session needed** to: run `enrich_facebook.py` (28-venue phone
  queue), and the OSM/Wongnai/Geofabrik bulk scrape for other provinces.
- Restaurant segment for Udon is started, not exhaustive.
- `venue_type` is `unknown` for ~2,100 directory rows (keyword classifier only).
- Don't expand to other cities until Udon is signed off (per product owner).
