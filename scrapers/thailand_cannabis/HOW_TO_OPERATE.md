# How to Operate — TH Cannabis Outreach

Practical operator guide. For technical/dev notes, see [README.md](README.md).

---

## 1. The 30-second mental model

You have **three layers**:

1. **Raw data** — CSV files in [data/](data/) produced by the scrapers (weed.th sitemap, Google Places enrichment, email scraping, lead scoring).
2. **SQLite database** — [data/outreach.sqlite](data/outreach.sqlite). Built from the CSVs by the import script. Holds your manual edits, status, notes, and activity log. **This is the file to back up.**
3. **Flask web app** — the UI you use to actually do outreach. Reads from the DB. Writes your edits and activity back to the DB.

```
  CSVs  →  import_csvs.py  →  outreach.sqlite  ↔  Flask app  →  browser
                                       ↑
                              (your manual edits + activity log live here)
```

Re-running scrapers refreshes the CSVs. Re-running `import_csvs.py` updates the shop columns in the DB **without** touching your outreach state.

---

## 2. Quick start (you just need to do outreach)

```powershell
# From the project root
python -m scrapers.thailand_cannabis.webapp.app
# Open http://127.0.0.1:8000 in your browser
```

Then:

1. Click a province on the homepage (e.g. **Chiang Mai** — highest density of high-quality leads).
2. Filter the table: **Status = new**, **Min score = 8**. That's your starting pool.
3. For each shop row, click **WhatsApp**. A new tab opens with WhatsApp Web (or mobile app) and a pre-filled message. **You click Send.**
4. The app auto-logs the action and marks the shop as `messaged`.
5. When a shop replies, open it (click the name), change status to `replied` (or `interested` / `no_answer`), add notes, save.

That's the loop. The rest of this doc is for when you need to refresh data, add/edit templates, troubleshoot, or extend.

---

## 3. Files & directories you'll touch

| Path | What it is |
|---|---|
| [scrapers/thailand_cannabis/webapp/](webapp/) | The Flask app (you never edit this for day-to-day use) |
| [scrapers/thailand_cannabis/data/](data/) | All output: CSVs, SQLite DB, HTML reports |
| [scrapers/thailand_cannabis/data/outreach.sqlite](data/outreach.sqlite) | **Your outreach state. Back this up.** |
| [scrapers/thailand_cannabis/data/leads_country.csv](data/leads_country.csv) | Master list of all 11,272 shops + phones + emails + scores |
| `data/leads_<city>.csv` | Per-city slices of the master list |
| `data/report_<city>.html` | Standalone HTML reports (no server needed, but no WhatsApp button) |
| [scrapers/thailand_cannabis/HOW_TO_OPERATE.md](HOW_TO_OPERATE.md) | This file |
| [scrapers/thailand_cannabis/README.md](README.md) | Developer / scraper docs |

---

## 4. One-time setup (only needed on a fresh machine)

### 4a. Install Python dependencies

```powershell
pip install -r requirements.txt
pip install flask
```

(Playwright is also installed for some scrapers but isn't needed for day-to-day operation.)

### 4b. Get the data files

Either you already have `data/leads_country.csv` etc. from a previous run, OR you re-run the whole pipeline (see section 7).

### 4c. Initialize the database

```powershell
python -m scrapers.thailand_cannabis.webapp.import_csvs
```

This creates `data/outreach.sqlite` and loads all 11,272 shops. It also seeds one default WhatsApp message template.

### 4d. Edit the default WhatsApp message

```powershell
python -m scrapers.thailand_cannabis.webapp.app
# Open http://127.0.0.1:8000/templates
```

The seeded template is generic. Replace it with whatever pitch you're actually using. `{shop_name}` and `{city}` are auto-substituted at send time.

---

## 5. Daily operation

### 5a. Start the server

```powershell
python -m scrapers.thailand_cannabis.webapp.app
```

Leave that terminal window open while you work. `Ctrl+C` stops the server.

### 5b. Pick your work for the day

Open **http://127.0.0.1:8000/** — the homepage shows all 79 provinces sorted by shop count. The columns tell you:

| Column | Meaning |
|---|---|
| **Shops** | Total shops in this province |
| **With phone** | Shops you can WhatsApp / call |
| **High quality (8+)** | Lead-quality score ≥ 8 — your best B2B prospects |
| **Messaged** | How many you've already contacted |
| **Replied** | How many replied |

**Where to start (highest leverage):**
- **Chiang Mai** — 223 HQ leads, 46 emails
- **Phuket** — 204 HQ leads, 79 emails (highest email rate)
- **Pattaya** — 181 HQ leads
- **Surat Thani** (incl. Koh Samui) — 120 HQ leads

Bangkok shows only 21 HQ leads but has 2,094 shops total. Most Bangkok matches are flagged "low confidence" by Google because the address format doesn't literally say "Bangkok" (sub-districts like Sukhumvit/Watthana are common). The 127 emails confirm Bangkok has lots of real operators — the score just underweights them.

### 5c. Working a city

Click into any city. You'll see:

- **Filter chips** at top: filter by status, min-score, sort order
- **Active template indicator**: shows which WhatsApp message will be sent
- **Shop table**: one row per shop

**Recommended filter for first outreach pass:** `status=new`, `min_score=8`.

Per-row actions (right column):

- **WhatsApp** — opens WhatsApp Web with pre-filled message. You hit Send. Auto-logs + bumps status to `messaged`.
- **Call** — opens your default `tel:` handler (Windows: Skype / Phone Link). Logs the action.
- **Email** — opens your default mail client. Logs the action.
- **Edit** — opens the shop detail page for manual edits.

### 5d. Recording results

When a shop replies (or doesn't), open it (click the name) and update:

| Status | When to use |
|---|---|
| `new` | Never contacted (default) |
| `messaged` | You sent a WhatsApp / made a call / sent email |
| `replied` | They responded (any response) |
| `interested` | They're a real lead (warm) |
| `no_answer` | Tried multiple times, no response |
| `closed` | Dead lead — either rejected or you decided to drop |

You can also enter **manual phone / email** (overrides what was scraped) and **notes** (free text — visit notes, context, anything).

The **Activity log** at bottom shows every action taken on this shop with timestamp.

---

## 6. Templates (message editing)

`http://127.0.0.1:8000/templates`

You can have multiple templates per channel (WhatsApp / email). Mark one as **default** per channel — it's what gets used when you click the WhatsApp button.

**Merge fields:**
- `{shop_name}` → the shop's name from weed.th
- `{city}` → the canonical province name

To use a non-default template on a specific shop: open the shop's detail page, click the template name in the **WhatsApp template picker** section, then click WhatsApp.

**Tip:** Create different templates per use case (e.g. "Bangkok intro", "Tourist-area intro", "Multi-shop operator pitch") rather than one generic one.

---

## 7. Refreshing data (re-running scrapes)

You only need this when:
- Time has passed (data goes stale; cannabis market is volatile post-June-2025)
- You want to add a new city or coverage area
- A scraper got new fields or fixes

### 7a. Just re-import existing CSVs into the DB

```powershell
python -m scrapers.thailand_cannabis.webapp.import_csvs
```

Refreshes the shop columns in the DB. **Your outreach state (status, notes, manual phone/email, activity log) is preserved.**

### 7b. Re-run the country Google Places enrichment (~$340 + 2-3 hours)

```powershell
# Need a Google Maps API key first — see section 9
$env:GOOGLE_MAPS_API_KEY = "AIza..."

# Run on weed.th's current sitemap (refresh the base list first if needed)
python scrapers/thailand_cannabis/scrape_weed_th.py
python scrapers/thailand_cannabis/enrich_google_places.py scrapers/thailand_cannabis/data/weed_th.csv --resume
```

`--resume` skips shops already enriched in the existing output file, so re-running is cheap if mostly unchanged.

### 7c. Re-run lead qualification + email scrape (~2-3 hours, free)

```powershell
python scrapers/thailand_cannabis/lead_qualify.py --country --resume
python scrapers/thailand_cannabis/split_leads_country.py
python -m scrapers.thailand_cannabis.webapp.import_csvs
```

### 7d. Update one specific city

If you only want fresh data for one city (e.g. Bangkok had a big change):

```powershell
# Optional: refresh Google data per-city (only if you've also re-scraped weed.th)
python scrapers/thailand_cannabis/enrich_google_places.py scrapers/thailand_cannabis/data/weed_th_bangkok.csv

# Refresh lead-quality + emails for the city
python scrapers/thailand_cannabis/lead_qualify.py "Bangkok"

# Re-import
python -m scrapers.thailand_cannabis.webapp.import_csvs
```

---

## 8. Backups

The only file that contains work you can't reproduce: **[data/outreach.sqlite](data/outreach.sqlite)**.

Everything else (CSVs, HTML) can be re-generated by re-running the scrapers. The SQLite DB holds your edits, statuses, notes, and activity log — which can't.

```powershell
# Take a snapshot before any risky operation
Copy-Item scrapers/thailand_cannabis/data/outreach.sqlite scrapers/thailand_cannabis/data/outreach.sqlite.bak

# Restore
Copy-Item scrapers/thailand_cannabis/data/outreach.sqlite.bak scrapers/thailand_cannabis/data/outreach.sqlite
```

For real backup, copy that file to OneDrive / Dropbox / external drive once a day.

---

## 9. Google Maps API key

You only need this if you re-run `enrich_google_places.py`.

### Set up (one time, ~5 min)

1. https://console.cloud.google.com — create or pick a project
2. **APIs & Services → Library** → enable **"Places API (New)"** ← must be the "(New)" one
3. **APIs & Services → Credentials → + Create credentials → API key**
4. **Edit API key** → restrict to "Places API (New)" only
5. **Billing** → link an account. Google gives $200/month free credit (~6,250 lookups).

### Use

```powershell
# Per-session (cleanest, key isn't stored anywhere)
$env:GOOGLE_MAPS_API_KEY = "AIza..."
python scrapers/thailand_cannabis/enrich_google_places.py ...

# Persist across PowerShell sessions
[Environment]::SetEnvironmentVariable("GOOGLE_MAPS_API_KEY", "AIza...", "User")
# Close and reopen PowerShell. From then on, just run the script.
```

**Never paste the key into a chat or commit it to git.** A leaked key bills against your account until you delete it (Google Console → Credentials → trash icon).

---

## 10. Cookbook — common tasks

### "Show me the 50 highest-quality shops in the country"

```powershell
# Quick CSV query
python -c @"
import csv
rows = []
with open('scrapers/thailand_cannabis/data/leads_country.csv','r',encoding='utf-8-sig',newline='') as f:
    rows = list(csv.DictReader(f))
rows.sort(key=lambda r: -int(r.get('lead_score') or 0))
for r in rows[:50]:
    print(f"{r['lead_quality']:>3}  {r['canonical_city']:<20}  {r['name']:<35}  {r.get('google_phone','-')}")
"@
```

### "Give me the emails of shops who have one"

```powershell
python -c @"
import csv
with open('scrapers/thailand_cannabis/data/leads_country.csv','r',encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f):
        if r.get('scraped_email'):
            print(f""{r['scraped_email']:<35} | {r['name']:<35} | {r.get('canonical_city','')}""))
"@
```

Or open `http://127.0.0.1:8000/search?q=@` to filter by emails in the UI (works because emails contain `@`).

### "Which phones are shared across multiple shops (multi-shop operators)?"

```powershell
python -c @"
import csv
from collections import defaultdict
by_phone = defaultdict(list)
with open('scrapers/thailand_cannabis/data/leads_country.csv','r',encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f):
        p = r.get('google_phone','').strip()
        if p:
            by_phone[p].append(f""{r['name']} ({r.get('canonical_city','')})"")
for phone, names in sorted(by_phone.items(), key=lambda kv: -len(kv[1])):
    if len(names) >= 3:
        print(f""{phone} ({len(names)} shops): {names[:3]}"")
"@
```

### "Export everyone I've contacted today"

```powershell
python -c @"
import sqlite3
c = sqlite3.connect('scrapers/thailand_cannabis/data/outreach.sqlite')
c.row_factory = sqlite3.Row
sql = '''SELECT s.name, s.canonical_city, s.google_phone, l.action, l.created_at
         FROM outreach_log l JOIN shops s ON s.source_id = l.source_id
         WHERE l.created_at >= date('now')
         ORDER BY l.created_at DESC'''
for r in c.execute(sql):
    print(f""{r['created_at']}  {r['action']:<20}  {r['name']:<35}  {r['canonical_city']}"")
"@
```

---

## 11. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Flask app won't start: "Address already in use" | Another copy is running on port 8000. Stop it (Ctrl+C in its terminal) or use `--port 8001`. |
| CSS / layout changes don't show up after edit | Restart Flask. Cache busting is in place but a server restart guarantees fresh templates. |
| WhatsApp button is missing on a shop row | That shop has no phone number on file. Add one via the Edit panel and save. |
| WhatsApp opens with empty message | No default template set. Visit `/templates` and check **Default** on at least one WhatsApp template. |
| WhatsApp opens but says "Number not on WhatsApp" | The phone is real but isn't registered with WhatsApp. Try `tel:` (Call button) instead, or LINE if available. Many Thai shops use LINE more than WhatsApp. |
| Phone numbers look wrong | The Edit panel lets you override what was scraped. Manual phone always wins over Google's value. |
| Score column shows `—` | That shop's `lead_quality` is NULL — usually because the `lead_qualify.py` run hasn't covered it yet. Re-run `import_csvs.py` after the lead-qualify completes. |
| All my outreach state disappeared | You probably ran the import on a fresh empty DB. Restore from `outreach.sqlite.bak` if you backed up. |

---

## 12. Things this system does **not** do (deliberate)

- **It does not send messages on your behalf.** WhatsApp opens with the message pre-filled; you click Send. This is intentional — sending automatically would violate WhatsApp's commerce policy and get your number banned.
- **It does not de-duplicate shops automatically.** weed.th has duplicate listings (e.g. same shop registered 2-3 times). They appear as separate rows. Use the manual `closed` status to remove duplicates from your working set.
- **It does not solve captchas, rotate IPs, or evade rate limits.** All scrapers respect declared crawl-delays.
- **It does not auto-refresh from weed.th.** Data ages. Re-run the scrapers periodically if you need fresh listings (section 7).
- **It does not have multi-user / login.** Single operator on one machine. If two people use it, edits will conflict.

---

## 13. Quick reference card

```powershell
# Start the app
python -m scrapers.thailand_cannabis.webapp.app

# Refresh DB from CSVs (keeps your edits)
python -m scrapers.thailand_cannabis.webapp.import_csvs

# Back up your work
Copy-Item scrapers/thailand_cannabis/data/outreach.sqlite scrapers/thailand_cannabis/data/outreach.sqlite.bak

# Re-run the country pipeline (slow + costs $$)
$env:GOOGLE_MAPS_API_KEY = "AIza..."
python scrapers/thailand_cannabis/scrape_weed_th.py
python scrapers/thailand_cannabis/enrich_google_places.py scrapers/thailand_cannabis/data/weed_th.csv --resume
python scrapers/thailand_cannabis/lead_qualify.py --country --resume
python scrapers/thailand_cannabis/split_leads_country.py
python -m scrapers.thailand_cannabis.webapp.import_csvs
```

URLs:

```
http://127.0.0.1:8000/                  homepage (all provinces)
http://127.0.0.1:8000/city/chiang_mai   work a city
http://127.0.0.1:8000/shop/<source_id>  per-shop detail
http://127.0.0.1:8000/templates         edit message templates
http://127.0.0.1:8000/search?q=...      search across all 11K
```
