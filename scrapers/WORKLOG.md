# Worklog — TH B2B lead-gen platform

Project-wide running log. Each entry: date, what was done, what's next.
For task-by-task narrative within a session, see git log on `master`.

---

## 2026-05-29 (later) — Hospitality vertical pivot + Wongnai investigation

**Scoping decided with user:**
- Start with Udon Thani as pilot (small, consistent with cannabis pilot)
- B2B angle: tourism / hospitality vertical
- Probe Wongnai first (free) before falling back to Google Places

**Wongnai investigation findings:**

- robots.txt is permissive (only `/users/` blocked), no Cloudflare challenge.
- **Found their private JSON API: `GET /_api/regions/{regionId}/businesses.json`** — server-side rendered + reachable without auth.
- Per-shop JSON-LD on detail pages has: name, address (with streetAddress), geo, **telephone**, openingHoursSpecification, aggregateRating, **priceRange (in baht)**, **servesCuisine** — richer than Google Places, free.
- **BUT region filtering is broken.** API for region `41000` (Udon Thani postcode) returned 35/36 entities — all in **Chiang Rai** (lat ~19.7, lng ~99.1, zipcodes 50170/50320). 0 actually in Udon Thani. The category filter (`categories.id`) is also ignored — every category returns the same 36 entities.
- Region counts: Bangkok (10100) → 10,929 entities; Pattaya (20150) → 2,080; Chiang Mai (50100) → 56; Phuket (83000) → 61; Udon Thani (41000) → 36. Suspiciously low for major cities — these likely aren't actually region-scoped either; just "popular nationwide" with different sort biases.

**Initial conclusion (later overturned):** Wongnai's URL filter is broken — `/regions/41000/businesses.json` returns Chiang Rai shops, not Udon Thani.

**Breakthrough on continued investigation:**
- Wongnai uses **slugs (lowercase, no hyphens) as region IDs in the API**, NOT postcodes.
- Correct endpoint: `GET /_api/regions/udonthani/businesses.json` → **2,245 real Udon Thani entities** (91/99 sampled within Udon Thani geo bounds, dominant zipcode prefix 41).
- Also discovered `/_api/regions.json` returns the full Wongnai region directory (107 cities) — saved to [thailand_hospitality/wongnai_regions.json](thailand_hospitality/wongnai_regions.json) for reuse. Slugs: `bangkok`, `chiangmai`, `phuket`, `khonkaen`, `udonthani`. Some longer ones use `regions/{id}-{thai-encoded-name}` format (e.g., Pattaya).
- Per-shop detail-page JSON-LD has phone, address, geo, hours, rating, priceRange (in baht), servesCuisine — richer than Google Places, free.

**Pivot:** Wongnai IS viable. Built [scrape_wongnai.py](thailand_hospitality/scrape_wongnai.py) + [enrich_wongnai_details.py](thailand_hospitality/enrich_wongnai_details.py).

**Outcome of first run:** Hit Wongnai's rate limit hard. Initial 1s crawl-delay triggered 403 at page 80. Bumped to 2.5s + 30s retry-backoff + --resume support; resumed run also got 403 immediately, including on the regions.json index endpoint — **IP-level ban, not endpoint-specific**. All Wongnai URLs return 403 from this IP. Standard recovery: 30 min to 24h.

**Partial data captured:** 1,417 of 2,245 (63%). Food/drink: 1,144. In-bounds Udon Thani: 91%. Decent pilot dataset; can supplement with Google Places to fill phone/website/hours.

**Lessons:**
- Wongnai's friendly robots.txt and rich public API hide aggressive IP-level rate limiting (~80 reqs in 2 min triggers ban).
- Use ≥5s crawl-delay for sustained runs. Better still, run during off-peak Thai hours.
- Detail-page enrichment (per-shop fetch) is even riskier; needs equally slow pacing or paid proxy.

**Ad-signal investigation (later same day):**

User asked to add ad-spending as a B2B signal via Facebook Ad Library + Google Ads Transparency Center.

- **FB Ad Library**: scrapable via Playwright with URL search. Built [check_fb_ads.py](thailand_hospitality/check_fb_ads.py). Discovery: `search_type=keyword_exact_phrase` dramatically reduces false positives vs `keyword_unordered` (generic Thai dish name went from 8,500 noise hits to a clean 0). Full run on 1,144 Udon Thani food shops kicked off in background, ETA ~1 hour.

- **Google Ads Transparency Center**: CRACKED THE RPC (vs cannabis project where we gave up).
  - Endpoint: `POST https://adstransparency.google.com/anji/_/rpc/SearchService/SearchSuggestions?authuser=`
  - Payload (URL-form-encoded): `f.req={"1":"<query>","2":10,"3":10,"4":[2764],"5":{"1":1}}`. Region 2764 = Thailand.
  - Response is JSON: `{"1": [{"1": name, "2": "AR...id", "3": "TH"/"US"/etc, ...}, ...]}`
  - No auth, no captcha, ~1.5s/req tolerated. Built [check_atc_ads.py](thailand_hospitality/check_atc_ads.py).
  - **HONEST NEGATIVE RESULT: 0/100 hits on Udon Thani food shops.** ATC only lists identity-verified advertisers (legal-document verification with Google). Small Thai SMBs essentially never verify. Even chains like Café Amazon returned 0 — only major brands (Bumrungrad Hospital, Lazada, AIS, Toyota) appear.
  - Pipeline works for any future use where the target IS a larger verified advertiser. For SMB hospitality lead-gen in Thailand, ATC ≈ useless signal.

**Round 2 — more sources probed (same day):**

- **FB Ad Library full run completed**: 104/1,144 (9%) of Udon Thani food shops have FB ads. Top 5 hits (50K+ ads each) are false positives from generic Thai names; the 2-100 ad range is the clean signal (~70 shops). [check_fb_ads.py](thailand_hospitality/check_fb_ads.py) output: [data/fb_ads_udonthani.csv](thailand_hospitality/data/fb_ads_udonthani.csv).

- **TikTok Ad Library**: cracked RPC at `POST /api/v1/suggestion`. Returns identity-verified TikTok advertisers. **0/30 hits on Udon Thani SMBs** — same verification-wall problem as Google ATC. Useless for SMBs.

- **TripAdvisor**: hard 403 (Cloudflare). Not worth fighting.

- **Search-engine pivot for FB page detection** (no auth way to detect FB pages directly):
  - Google / Bing / Yandex / DDG / Mojeek / Startpage — all bot-block.
  - **Brave Search works** but rate-limits at ~5 requests then blocks. Confirmed signal is real (4/4 first-batch shops had FB pages) but doesn't scale free.

- **Delivery platforms (Grab Food / LINE MAN / Foodpanda)** — ALL dead end for web scraping. Grab is app-only with marketing-only web pages. LINE MAN same. **Foodpanda exited Thailand in 2024** (URL redirects to a deep-link to successor service).

- **Hotel sources**: most blocked (Hotels.com 429 "Bot or Not?", Klook 403, Booking.com 202 rate-limited, Agoda has CF challenge in body). Trip.com loads 271KB but is JS-rendered (no data in initial HTML). **OSM (Overpass) is the winner**: 220 unique Udon Thani hospitality POIs (98 hotels + 30 guesthouses + 28 bars + 20 attractions + 15 motels + smaller), 26% with phone, 10% with real website. [scrape_osm.py](thailand_hospitality/scrape_osm.py) → [data/osm_udonthani.csv](thailand_hospitality/data/osm_udonthani.csv).

**Combined hospitality dataset for Udon Thani (after this session):**
- Wongnai restaurants/cafes: 1,417 (1,144 food)
- OSM hotels + nightlife + attractions: 220
- FB ads signal: 104 paid advertisers (overlaid on Wongnai)
- Total unique businesses: ~1,500 (some overlap between sources)

**Outstanding for next session:**
- Wait for Wongnai IP unblock (~24h) → fill missing 828 + run detail enrichment for phone/cuisine/price
- User to set Google Maps API key → run enrich_google_places.py on Wongnai data (~$36, ~1 hour)
- Build hospitality lead-scoring formula combining FB ads + reviews + website type + tourism-category bias
- Build deduplication between Wongnai and OSM (same shops likely in both)

**Same session, later — Hospitality merge + score + country expansion:**

- Built [merge_hospitality.py](thailand_hospitality/merge_hospitality.py) (dedup Wongnai ∪ OSM, weight by signals) + [report_hospitality.py](thailand_hospitality/report_hospitality.py).
- Udon Thani output: 1,636 unique businesses, 551 tourism-relevant, 15 score-5+ (mostly hotels with phone+website), 61 score-3-4 (mostly cafés/bars running FB ads). Only 1 cross-source merge — Wongnai (restaurants) and OSM (lodging) cover different verticals.
- **Wongnai IP unbanned** (verified via /_api/regions.json HTTP 200). Entity counts re-probed for tourism cities: Bangkok 809K, Phuket 40K, Chiang Mai 40K, Pattaya 14K (slug `1009-pattaya`), Krabi 13K, Surat Thani 15K, Hua Hin 12K, Chiang Rai 8.5K, Khon Kaen 33K, Korat 45K. Ayutthaya slug returns Chonburi shops (bad mapping — skip).
- **User pivot: scale to whole-country reachable contact list (restaurants/bars).** Built [run_all_cities.py](thailand_hospitality/run_all_cities.py) orchestrator + [run_phase3_details.py](thailand_hospitality/run_phase3_details.py) + [run_phase4_fbads.py](thailand_hospitality/run_phase4_fbads.py) + [aggregate_country.py](thailand_hospitality/aggregate_country.py).
- Kicked off autonomous 4-phase chain in background, target: 11 cities × 2K bulk + 500 detail-enrichment per city + FB ads check per city + final country aggregation. Total runtime ~11-12h, output: master `hospitality_country.csv` + `reachable_country.csv` + per-city HTML reports.
- User instruction: "do not stop with questions during crawl, you have all approvals."

**New requirement from user (mid-investigation):** Add ad-spending as a B2B prospect signal. Investigate:
- Google Ads Transparency Center (previously failed to scrape for cannabis — same surface)
- Facebook Ad Library (publicly accessible; most Thai SMBs run FB ads, so probably the more useful source)
- Maps-Sponsored detection
- Inference from existing signals (already in lead-quality score)
- Recommend Facebook Ad Library probe first since it's known scrapable + Thai SMBs are FB-heavy.



**Cannabis project (continuation of 05-28):**

- Country-wide Google Places enrichment completed: **11,272 shops, 9,545 phones (85%), 433 emails (3.8%), ~$360 spent.**
- Country-wide lead-qualification + email scrape completed. Top tiers: 19 shops at score 10, 245 at 9-10, 2,629 at 8+.
- City normalization: 107 raw city values collapsed to 79 canonical Thai provinces (Chang Wat prefix stripping + Thai-script aliases + spelling fixes via [city_normalize.py](thailand_cannabis/city_normalize.py)).
- Flask web app built: cities index, per-city table, per-shop edit, message templates, search. WhatsApp click-to-chat via wa.me with template merge. Outreach state in SQLite, preserved across CSV re-imports.
- Filters added: hide low-confidence Google matches (default ON), group by phone (default ON). Bangkok went from "unusable 2,094-row noise" to a clean working list.
- Dedicated Reviews column added to city table.
- Operator guide: [thailand_cannabis/HOW_TO_OPERATE.md](thailand_cannabis/HOW_TO_OPERATE.md).

**Outstanding / known issues:**

- Bangkok confidence heuristic is buggy — Google returns sub-district addresses (Watthana, Sukhumvit) that don't contain "Bangkok" literally, so most real Bangkok shops get flagged `low_conf` and hidden by the new filter. Workaround for now: toggle the "Show all" chip on Bangkok pages. Real fix: extend [enrich_google_places.py](thailand_cannabis/enrich_google_places.py)'s `confidence()` function to know about Bangkok sub-districts.
- Many top-Bangkok results are wrong businesses (hotels, malls, hostels) matched to weed.th shop names — Google Places false positives. The new low-conf filter masks most of them but a few high-conf misses slip through.
- weed.th authenticated scraping (`weed_th_auth_*.py`) is built but not used — the Google Places path got us 85% phone coverage which is enough.

**Next:** pivot to restaurants + bars market analysis (separate project, will reuse the pipeline).

---

## 2026-05-28 — Cannabis project bootstrap

**Built from scratch:**

- Source survey. Probed weed.th, thaidispos.com, cannabisforthailand.com, WeedMaps Thailand (404), GanjaCheck (doesn't exist).
- weed.th bulk scraper ([thailand_cannabis/scrape_weed_th.py](thailand_cannabis/scrape_weed_th.py)): one sitemap fetch → 11,271 unique shops with city+name (no detail pages needed).
- thaidispos scraper ([thailand_cannabis/scrape_thaidispos.py](thailand_cannabis/scrape_thaidispos.py)): 8 licensed dispensaries with full structured data via JSON-LD.
- Cross-reference logic ([thailand_cannabis/merge.py](thailand_cannabis/merge.py)): word-set Jaccard ≥ 0.4 (after first try with SequenceMatcher gave 4 false positives).
- HTML reports: country summary + per-city directory + ad-check shortlist.

**Discoveries worth remembering:**

- **Cannabis was reclassified as a controlled substance in Thailand in June 2025.** Most weed.th shops likely closed / unlicensed / in limbo.
- **weed.th gates phone numbers behind login.** Public API returns `"phone":true` flags only. Authenticated `user.getDispensaryContactInfo` returns the actual value. Light XOR obfuscation on public blob (base64 + XOR with key `1234567890`) but only encodes metadata, not contact values.
- **Udon Thani has 0% scrapable emails** — every "website" is a Facebook page. Email channel barely exists for this market.
- **Multi-shop operators identifiable via shared phone**: one Udon Thani phone (098 241 4764) covers 8 listings. Highest-leverage B2B targets.
- **Google Places API key was leaked into chat** mid-session. Rotated after run.

**Manual edit UI** (per-city HTML reports): localStorage-backed editor for phone/email/notes per shop with CSV export/import.

**Stage 2 enrichment**: Google Places API (Path B). Set up: $200/mo free credit, ~$0.03/shop with contact fields. Used Udon Thani as pilot (135 shops, ~$4, 79% phone hit rate).

---

## Pipeline components (reusable across verticals)

The cannabis project built these generic pieces — they work for any list of Thai businesses with names + cities:

| Component | What it does | Reusable for restaurants? |
|---|---|---|
| [thailand_cannabis/common.py](thailand_cannabis/common.py) | Dispensary dataclass, fetch helpers, JSON-LD parser, name normalization, sitemap parser | Yes — rename Dispensary, otherwise unchanged |
| [thailand_cannabis/city_normalize.py](thailand_cannabis/city_normalize.py) | Canonical Thai province names | Yes — directly |
| [thailand_cannabis/enrich_google_places.py](thailand_cannabis/enrich_google_places.py) | Per-row Places API enrichment with crash-safe streaming | Yes — directly, just point at a different input CSV |
| [thailand_cannabis/lead_qualify.py](thailand_cannabis/lead_qualify.py) | Email scrape + lead-quality scoring + top-N shortlist | Yes — scoring weights might want tweaking per vertical |
| [thailand_cannabis/webapp/](thailand_cannabis/webapp/) | Flask app with WhatsApp click-to-chat | Yes — schema is generic shops + outreach, just point at a different DB or merge a vertical column |
| [thailand_cannabis/scrape_weed_th.py](thailand_cannabis/scrape_weed_th.py) | weed.th-specific sitemap | No — cannabis-only |

**For new verticals**, what we need is a fresh **discovery step** (list of shops in the vertical). Everything else flows through unchanged.
