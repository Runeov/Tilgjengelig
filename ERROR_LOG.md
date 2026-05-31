# ERROR LOG — what went wrong, why, and how to improve

Handoff companion to `WORKLOG.md`. Each entry: symptom → cause → fix → prevention.

## A. Environment / infrastructure

### A1. Live network egress blocked (the big one)
- **Symptom:** every request to `overpass-api.de`, `nominatim.openstreetmap.org`,
  `www.wongnai.com`, `download.geofabrik.de`, `facebook.com` returns **HTTP 403**.
  `WebFetch` is also 403 on all external sites.
- **Cause:** the Claude Code web session was created with a restrictive network
  policy (pypi/github only). Egress is fixed at session/environment creation; it
  **cannot be changed from inside a running session** by the agent or the user.
- **Impact:** no live scraping, no Facebook scraping, no bulk OSM. All venue
  enrichment had to come from **WebSearch result summaries** (which route through
  Anthropic infra and *do* work).
- **Fix / how to improve:** start a **new web session on this branch** with an
  open or allowlisted egress policy (hosts in `SCRAPING_SYSTEM.md`). Then
  `enrich_facebook.py` and the OSM/Wongnai scrapers run unchanged. Tools already
  fail fast with a clear message (`--check` preflights).

### A2. Bash working directory resets between calls
- **Symptom:** repeated `FileNotFoundError: data/...` and `pathspec ... did not
  match` — scripts ran from the wrong directory.
- **Cause:** the shell cwd did not persist as expected across tool calls; a
  trailing `cd` in one compound command shifted context for the next.
- **Fix:** always use absolute paths or a leading `cd /abs/path && ...` in the
  *same* command. Git commands must run from the repo root.
- **Prevention:** scripts resolve their own paths via `__file__`; operators
  should `cd` explicitly at the start of each command block.

### A3. git push rejected (non-fast-forward)
- **Symptom:** `! [rejected] ... (fetch first)` — the remote branch had advanced
  (parallel runbook commits).
- **Fix:** `git fetch origin <branch> && git rebase origin/<branch>` then push.
  The commit helper now retries with fetch+rebase on failure.

## B. Code bugs (caught, mostly by self-tests)

### B1. SQLite: expression in UNIQUE constraint
- **Symptom:** `sqlite3.OperationalError: expressions prohibited in PRIMARY KEY
  and UNIQUE constraints` on `init`.
- **Cause:** table-level `UNIQUE(name, COALESCE(city,''), COALESCE(address,''))`.
- **Fix:** moved to a `CREATE UNIQUE INDEX ... COALESCE(...)` (indexes allow
  expressions). `INSERT OR IGNORE` still honours it.

### B2. Phone normalisation (landline) wrong
- **Symptom:** `042-247-450` → `+66 4 224 7450` (should be `+66 42 247 450`).
- **Cause:** a length-conditional split that mis-grouped 8-digit national numbers.
- **Fix:** single split `+66 {b[:2]} {b[2:5]} {b[5:]}` for both 8- and 9-digit
  national numbers. **Caught by `enrich_facebook.py --selftest`** before any use.

### B3. `cmd_stats` invalid f-string
- **Symptom:** would-be `SyntaxError` from escaped quotes / backslashes inside an
  f-string expression.
- **Fix:** pulled the SQL into named variables; simplified the function.

### B4. `import-udon` wrong repo-root path
- **Symptom:** `ModuleNotFoundError: No module named 'krobjob'`.
- **Cause:** used 2 `dirname()` calls; the package root is 3 levels up from
  `scrapers/thailand_hospitality/enrich_city.py`.
- **Fix:** 3× `dirname`.

### B5. Seed double-counted contacts
- **Symptom:** `enriched from contacts: 150` for 75 venues.
- **Cause:** overlay read both the new standard file and the legacy file.
- **Fix:** `contacts_paths()` prefers `contacts_<slug>.csv`; legacy only used if
  the standard file is absent.

### B6. Self-test polluting the shared method log
- **Symptom:** `enrich_city selftest` wrote Testville rows into
  `_enrichment_log.csv`, skewing `proven`.
- **Fix:** `log()` ignores slugs starting with `_`.

## C. Data-quality issues (handle in QA before outreach)

- **C1. Cross-border venues.** Udon Thani's OSM bbox spills into **Vientiane,
  Laos**; ~14 Lao-script venues + several English-named Vientiane bars (Anou
  Cabaret, Seng Champa, Highland Bar, GO-DUNK, Moonlight Lounge) were wrongly in
  the Udon list. → excluded; filter by province/bbox properly in scraping.
- **C2. Government false-positives.** 6 `public_building` rows matched the
  bar/show keyword heuristic. → excluded; tighten classifier.
- **C3. Duplicate/shared phone.** Boyzone Pub's search summary returned the same
  number as White Box (093-424-4930) → kept address, flagged phone "verify".
- **C4. Closed/renamed venues.** e.g. Nuchy Music Bar (closed), Harry's
  HandleBar → Full Throttle, The ShaDow → T-Sood. → verify before contacting.
- **C5. Provenance.** All contacts are **search-summary-derived**, not
  authoritative. The `source` column records this. Verify before outreach.
- **C6. `venue_type` gaps.** ~2,100 directory rows are `unknown` (classifier only
  fires on clear keywords). → improve classifier or enrich from Wongnai
  categories when network is available.

## How we improve (priorities)

1. Run the **network-enabled session** → unlocks FB backfill + bulk scrape; kills
   the biggest constraint (A1).
2. Keep all harvest going through `enrich_city.add()` so the **method log** grows
   and the proven-ways report guides the next city.
3. Add a **verification pass** (C-series) before any outreach: dedupe phones,
   drop cross-border/closed, confirm via the venue's own FB/website.
4. Improve the `venue_type` classifier (C6) and the OSM bbox/clip (C1).
