# Data sources — Thailand hospitality (restaurants, bars & shows)

Running catalogue of sources we scrape from, plus researched candidates to add.
Keep appending as we evaluate more. "Allowlist host" is what a session's network
policy must permit (see `SCAN_REST_OF_THAILAND.md`).

Legend — **Status**: ✅ live · 🛠️ built, pending live validation · 🔬 candidate
(evaluated, not yet built) · 🚫 rejected (ToS / not feasible). **Access**: API =
documented API · HTML = scrape rendered pages · Bulk = downloadable dataset.

---

## Currently used (live)

| Source | Access | Allowlist host | Gives | venue_type coverage |
|--------|--------|----------------|-------|---------------------|
| **OpenStreetMap / Overpass** | API | `overpass-api.de` | name, lat/lon, amenity tags, phone/web/opening_hours when tagged | **bar** (`bar\|pub\|nightclub\|stripclub`), **show** (`theatre\|cinema\|arts_centre`, `stadium\|dance`, `muay_thai\|boxing`, `theme_park`), lodging/attraction/spa |
| **Nominatim** | API | `nominatim.openstreetmap.org` | geocodes province name → bounding box for Overpass | n/a (geocoder) |
| **Wongnai** | HTML | `www.wongnai.com` | restaurant + bar listings, name, area, cuisine, links | restaurants + **bar** (pub/bar rows tagged) |

OSM is the spine (free, redistributable under ODbL). Wongnai adds restaurant/bar
density OSM lacks. Bottleneck: Wongnai IP-bans ~80 req/2min → 15s delay + resume passes.

---

## Candidates to add (researched)

### Tier 1 — best fit for bars & shows, worth building next

| Source | Status | Access | Allowlist host | Why / what it adds | Notes & caveats |
|--------|--------|--------|----------------|--------------------|-----------------|
| **OSM bulk (Geofabrik / Planet)** | 🛠️ | Bulk | `download.geofabrik.de` | Whole-Thailand `.osm.pbf`, parsed offline via `pyrosm` | **Built:** `scrape_geofabrik.py` (drop-in for `scrape_osm.py`, same schema/`venue_type`). **Removes Overpass rate-limit entirely.** One download covers all 77 provinces. Logic self-tested offline; pyrosm parse pending a networked run. Best ROI. |
| **BK Magazine** | 🔬 | HTML | `bkmagazine.com` | Curated Bangkok bars / live-music venues / nightlife — strong **show** + cocktail-bar signal OSM misses | Editorial lists, low volume, high quality. Bangkok-centric. |
| **Time Out Bangkok** | 🔬 | HTML | `timeout.com` | Bars, rooftop, live music, cabaret listings | Similar to BK Mag; cross-source to dedupe. |
| **Siam2nite** | 🔬 | HTML | `siam2nite.com` | Club/party/event venues nationwide — **bar/club** focus | Event-driven; good for nightlife venue discovery. |
| **Ticketmelon** | 🛠️ | HTML/API | `ticketmelon.com` | Ticketed live **shows** / concerts / Muay Thai / cabaret + venue | **Built:** `scrape_ticketmelon.py` (events→`venue_type=show`, parses `__NEXT_DATA__`/`ld+json`). Mapping self-tested offline; JSON key paths + merge wiring pending a networked run. Strongest pure "show" source. |

### Tier 2 — restaurant/bar density & contact enrichment

| Source | Status | Access | Allowlist host | Why / what it adds | Notes & caveats |
|--------|--------|--------|----------------|--------------------|-----------------|
| **Tripadvisor** | 🔬 | HTML | `tripadvisor.com` | Restaurants + bars + "fun & games"/shows, ratings, reviews, nationwide incl. tourist towns | Aggressive anti-bot; needs headless browser + slow rate. ToS prohibits scraping — review before use. |
| **Eatigo** | 🛠️ | HTML/API | `eatigo.com` | Reservation-discount restaurants incl. many bars/buffets, by region | **Built:** `scrape_eatigo.py` (region pages → restaurant/bar rows via `__NEXT_DATA__`, cuisine→`venue_type`). Mapping self-tested offline; `pageProps` shape + merge wiring pending a networked run. |
| **Hungry Hub** | 🔬 | HTML/API | `hungryhub.com` | #1 TH reservation app — buffet/à-la-carte venues, contact + booking | Good for contactable/outreach subset. |
| **GrabFood** | 🔬 | HTML/API | `grab.com` | Huge delivery restaurant coverage incl. small local spots | JS-heavy; per-area listing pages. Delivery ≠ dine-in/bar. |
| **Zomato** | 🔬 | API/HTML | `zomato.com` | Restaurant + **bar/cocktail/beverage** menus, SEA coverage | Has bar-menu depth (cocktails/whisky/beer). API access gated. |

### Tier 3 — commercial POI APIs (paid, easy, license-restricted)

| Source | Status | Access | Allowlist host | Why / what it adds | Notes & caveats |
|--------|--------|--------|----------------|--------------------|-----------------|
| **Google Places API** | 🔬 | API | `maps.googleapis.com` | Broadest global coverage, ratings, hours, phone | **API key + billing.** ToS forbids storing/redistributing most fields → conflicts with building our CSV dataset. |
| **Foursquare Places** | 🔬 | API | `api.foursquare.com` | Rich POI metadata, good granular categories/alt-names | License is revocable, "use in-app only" — **cannot redistribute** our dataset. |
| **Geoapify Places** | 🔬 | API | `api.geoapify.com` | OSM data via simple category/area HTTP queries (no Overpass syntax) | Free tier; **OSM-derived so ODbL-friendly.** Easiest API on-ramp. |

---

## Selection guidance

- **Best next build:** OSM bulk (Geofabrik) — kills the rate-limit problem and is
  license-clean. Then Tier-1 editorial sources (BK Mag, Time Out, Siam2nite,
  Ticketmelon) for the **show** category, which OSM tags sparsely.
- **License watch:** Google/Foursquare forbid building a redistributable dataset —
  fine for live lookups, **not** for our committed CSVs. Prefer OSM-derived
  (Overpass, Geoapify, Geofabrik) for anything we store/publish.
- **Always:** respect robots.txt + ToS, rate-limit (per-host delay like Wongnai's
  15s), and dedupe across sources by name+geo before merging into
  `hospitality_<slug>.csv` / `hospitality_country.csv`.

## Add-a-source checklist

1. New `scrape_<source>.py` returning rows with our schema (incl. `venue_type`).
2. Add its host to the allowlist table in `SCAN_REST_OF_THAILAND.md`.
3. Wire dedupe/merge in `merge_hospitality.py`.
4. Add a row above; flip 🔬 → ✅ once it runs end-to-end.

---

### Sources consulted (research)

- [3i Data Scraping — restaurants & bars list](https://www.3idatascraping.com/scrape-restaurants-and-bars-list/)
- [Zyte — restaurant data scraping](https://www.zyte.com/data-types/restaurant-data-scraping/)
- [iWebScraping — Yelp/Tripadvisor restaurants & bars](https://www.iwebscraping.com/restaurants-bars-contact-directory-scraping.php)
- [tendem.ai — TripAdvisor scraping guide 2026](https://tendem.ai/blog/tripadvisor-scraping-hotels-restaurants-reviews)
- [Geoapify — 3 ways to get OpenStreetMap data](https://www.geoapify.com/ways-to-get-openstreetmap-data/)
- [wcedmisten.fyi — 6 open-source tools to query OSM](https://wcedmisten.fyi/post/how-to-query-osm/)
- [ScrapingBee — best Google Places API alternatives 2026](https://www.scrapingbee.com/blog/best-google-places-api/)
- [Geoapify (DEV) — Google Places API alternatives 2026](https://dev.to/geoapify-maps-api/google-places-api-alternatives-which-poi-api-should-you-use-in-2026-hd4)
- [Nomad eSIM — best food/booking apps in Bangkok](https://www.nomadesim.com/destination-guides/best-food-apps-bangkok)
- [Eatigo — Bangkok reservation platform](https://eatigo.com/en/regions/28)
- [Hungry Hub](https://apps.apple.com/gb/app/hungry-hub-dining-offer-app/id879303325)
- [BK Magazine — best live-music venues in Bangkok](https://www.bkmagazine.com/nightlife/10-best-venues-to-find-live-music-bangkok/)
- [Party Bangkok — nightlife (Siam2nite, BK Magazine)](https://partybangkok.com/nightlife/)
- [Expats in Bangkok — live music events](https://expatsinbangkok.com/event/concerts-bar-pub-live-music)
