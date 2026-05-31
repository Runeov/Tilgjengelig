# OPERATING — how to run KrobJob + the city scraper

Operator guide for cowork. Pure Python, stdlib only (CRM); scrapers add
`requests`/`beautifulsoup4` and optionally `playwright`/`pyrosm`. Branch:
`claude/gracious-ride-CN6xL`.

## 0. Setup

```bash
pip install -r requirements.txt   # requests, bs4, lxml (from repo root)
# optional for scraping: pip install playwright pyrosm
export KROBJOB_DB=krobjob/krobjob.db        # optional; this is the default
```

## 1. Initialise + load the directory

```bash
python -m krobjob init                       # create SQLite schema
python -m krobjob seed-udon                  # load Udon (hospitality + contacts)
# any other city, once its hospitality_<slug>.csv + contacts_<slug>.csv exist:
python -m krobjob seed-city rayong --province "Rayong"
python -m krobjob stats
```

## 2. Day-to-day CRM

```bash
# browse / inspect
python -m krobjob company list --venue-type bar --missing-contact --limit 40
python -m krobjob company show "Irish Clock"
python -m krobjob company add "New Venue" --province "Udon Thani" --venue-type bar --phone ...

# client lifecycle (registers on the KrobJob app)
python -m krobjob promote "Irish Clock" --plan growth --manager Nok --fee 8000

# communications & contracts
python -m krobjob comm log "Irish Clock" --channel facebook --direction out --subject "Onboarding" --body "..."
python -m krobjob comm list "Irish Clock"
python -m krobjob contract add "Irish Clock" --title "Retainer" --status active --value 96000 --start 2026-06-01 --end 2027-06-01
python -m krobjob contract list

# social (for marketing)
python -m krobjob social add "Irish Clock" --platform instagram --url ... --followers 1200
python -m krobjob social scan "Irish Clock"
```

## 3. Sales & expenses (the KrobJob app data feed)

```bash
python -m krobjob sale    log "Irish Clock" --amount 12000 --category drinks --date 2026-05-30
python -m krobjob expense log "Irish Clock" --amount 4000  --category "staff wages"
```

## 4. The recommendation agent

```bash
python -m krobjob report "Irish Clock" --days 30 --html      # per-client perf + advice
python -m krobjob trends --province "Udon Thani" --html      # market opportunity scan
```
- Runs **offline** (heuristics) by default. For richer prose, set
  `ANTHROPIC_API_KEY` (+ network) and it calls Claude automatically; `--no-claude`
  forces heuristics. HTML lands in `krobjob/reports/` (git-ignored).

## 5. Harvest contacts for a city (the proven method)

Run web searches per venue, record through the engine (this also logs the method):
```python
# from scrapers/thailand_hospitality/
import enrich_city
enrich_city.add("udonthani", [
  {"name": "Some Bar", "venue_type": "bar", "phone": "+66 ...",
   "facebook": "https://facebook.com/...", "address": "...",
   "query": "Some Bar Udon Thani phone address facebook"},
], city="Udon Thani", province="Udon Thani")
```
```bash
python enrich_city.py stats udonthani        # coverage
python enrich_city.py proven                 # which templates/sources yield contacts
```
Query templates + proven source domains live in `enrich_city.QUERY_TEMPLATES` /
`PROVEN_SOURCES`. Full playbook: `SCRAPING_SYSTEM.md`.

## 6. Network-only steps (need an egress-enabled session)

> The default web session blocks these (403). Start a session whose policy
> allows the hosts in `SCRAPING_SYSTEM.md`, then:

```bash
# Facebook phone backfill for venues with a FB page but no phone
python scrapers/thailand_hospitality/enrich_facebook.py --check
python scrapers/thailand_hospitality/enrich_facebook.py
python scrapers/thailand_hospitality/enrich_facebook.py --merge

# Bulk OSM (no rate limit) / per-province scrape
python scrapers/thailand_hospitality/scrape_geofabrik.py --download
python scrapers/thailand_hospitality/run_remaining_provinces.py --check
```

## 7. Onboarding a new city (checklist)

1. Scrape → `data/hospitality_<slug>.csv` (OSM/Wongnai/Geofabrik).
2. Harvest contacts via `enrich_city.add(...)`; check `enrich_city.py proven`.
3. `python -m krobjob seed-city <slug> --province "<Province>"`.
4. `enrich_facebook.py` in a network session.
5. `python -m krobjob trends --province "<Province>"`.

## Verify before outreach (QA)

Per `ERROR_LOG.md` section C: drop cross-border (Vientiane) and closed/renamed
venues, de-dupe suspicious shared phones, and confirm against the venue's own
Facebook/website. All contacts are search-derived until verified.

## Health checks

```bash
python -m krobjob stats
python scrapers/thailand_hospitality/enrich_city.py selftest
python scrapers/thailand_hospitality/enrich_facebook.py --selftest
python -c "import krobjob.cli, krobjob.agent, krobjob.seed; print('imports OK')"
```
