"""Lead-qualify shops in a city: scrape emails from websites, score each shop
by B2B-prospect signals, and produce a top-N shortlist for manual
Google-Ads-Transparency-Center spot-checks.

Inputs:
  data/weed_th_<city>_google.csv  (preferred — has google_website, google_phone, etc.)
  OR data/weed_th_<city>.csv      (basic fallback)
  OR filters data/weed_th_google.csv by city (country scrape fallback)

What this does:
  1. For each shop with a website, fetch homepage (5s timeout, no SSL strictness)
     and extract email addresses (mailto: hrefs + visible text patterns).
     Filters out generic placeholders (noreply@, privacy@, webmaster@, etc.).
  2. Computes a lead-quality score 0-10 from these signals:
       +3   has website
       +2   has phone (Google-sourced)
       +2   high-confidence Google match
       +1   has email (newly scraped)
       +up to 3 from log10(review_count+1)
  3. Writes data/leads_<city>.csv with all original fields + scraped_email +
     lead_quality + lead_score (raw 0-11).
  4. Writes data/top30_adcheck_<city>.html — a shortlist of the top N shops
     ranked by lead_quality, with one-click Transparency Center search URLs
     and Google Maps links so you can manually verify advertiser activity.

Usage:
  python lead_qualify.py "Udon Thani"
  python lead_qualify.py "Udon Thani" --top 50         # bigger shortlist
  python lead_qualify.py "Udon Thani" --skip-emails    # only score, no fetches
"""

import argparse
import csv
import html
import math
import os
import re
import sys
import time
from urllib.parse import urlparse

import requests
import urllib3
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.thailand_cannabis.common import DATA_DIR  # noqa: E402
from scrapers.thailand_cannabis.city_normalize import canonical_city  # noqa: E402

# Some Thai dispensary sites use expired/self-signed certs. We disable verification
# but suppress the noisy warning since this is a read-only scrape.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
JUNK_LOCAL_PARTS = {
    "noreply", "no-reply", "do-not-reply", "privacy", "webmaster",
    "abuse", "postmaster", "support@example", "you@example",
}
JUNK_DOMAIN_SUFFIXES = ("example.com", "test.com", "wixpress.com", "sentry.io")

# Hosts that don't have scrapable emails — social/link-aggregator/QR landing services.
# We skip fetches for these (saves ~65% of fetch time in the Thai cannabis data).
SOCIAL_HOSTS = {
    "facebook.com", "m.facebook.com", "web.facebook.com", "fb.me", "fb.com",
    "instagram.com", "instagr.am",
    "line.me", "lin.ee",
    "tiktok.com", "vm.tiktok.com",
    "twitter.com", "x.com",
    "youtube.com", "youtu.be",
    "t.me", "telegram.me",
    "linktr.ee", "beacons.ai", "bio.link", "heylink.me",
    "taplink.cc", "url.in.th", "bit.ly", "tinyurl.com",
    "canva.com", "shopee.co.th", "lazada.co.th",
}

FETCH_TIMEOUT = 6
FETCH_DELAY = 0.5  # between site fetches, courtesy


def load_input(city: str | None) -> tuple[list[dict], str]:
    """Same fallback chain as report_city.load_city_csv.

    If city is None, loads the full country file weed_th_google.csv.
    """
    country = os.path.join(DATA_DIR, "weed_th_google.csv")
    if city is None:
        if not os.path.exists(country):
            raise SystemExit(f"Country file {country} not found. Run enrich_google_places.py on weed_th.csv first.")
        with open(country, "r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f)), country
    safe = city.lower().replace(" ", "_")
    enriched = os.path.join(DATA_DIR, f"weed_th_{safe}_google.csv")
    basic = os.path.join(DATA_DIR, f"weed_th_{safe}.csv")
    if os.path.exists(enriched):
        with open(enriched, "r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f)), enriched
    if os.path.exists(basic):
        with open(basic, "r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f)), basic
    if os.path.exists(country):
        target = canonical_city(city).lower()
        with open(country, "r", encoding="utf-8-sig", newline="") as f:
            rows = [r for r in csv.DictReader(f)
                    if canonical_city(r.get("city", "")).lower() == target]
        if not rows:
            raise SystemExit(f"No rows for {city!r} in {country}.")
        return rows, country
    raise SystemExit(f"No data file found for {city!r}.")


def looks_like_real_email(addr: str) -> bool:
    local, _, domain = addr.partition("@")
    if not local or not domain:
        return False
    if local.lower() in JUNK_LOCAL_PARTS:
        return False
    if any(domain.lower().endswith(s) for s in JUNK_DOMAIN_SUFFIXES):
        return False
    # Filter image-filename false positives like "image@2x.png"
    if re.search(r"\.(png|jpg|jpeg|gif|svg|webp|woff|css|js)$", addr, re.I):
        return False
    if local.startswith(".") or local.endswith("."):
        return False
    return True


def extract_emails(html_text: str) -> list[str]:
    """Return a deduped list of plausible email addresses from page HTML."""
    found: list[str] = []
    seen: set[str] = set()

    # mailto: hrefs are most reliable
    for m in re.finditer(r'href=["\']mailto:([^"\'?]+)', html_text, re.I):
        e = m.group(1).strip()
        e_low = e.lower()
        if e_low not in seen and looks_like_real_email(e):
            seen.add(e_low)
            found.append(e)

    # Visible text email patterns (after stripping script/style)
    try:
        soup = BeautifulSoup(html_text, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ")
    except Exception:
        text = html_text

    for m in EMAIL_RE.finditer(text):
        e = m.group(0).strip(".,;:")
        e_low = e.lower()
        if e_low not in seen and looks_like_real_email(e):
            seen.add(e_low)
            found.append(e)

    return found


def is_social_url(url: str) -> bool:
    """True if the URL host is a social/link-aggregator service (no scrapable emails)."""
    if not url:
        return False
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    host = host.lower().lstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host in SOCIAL_HOSTS


def fetch_homepage(url: str) -> str | None:
    if not url or not url.startswith(("http://", "https://")):
        return None
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/148.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
            },
            timeout=FETCH_TIMEOUT,
            verify=False,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype.lower():
            return None
        return resp.text
    except Exception:
        return None


def _flush_partial(rows: list[dict], out_csv: str) -> None:
    """Write current rows to disk so a crash doesn't lose work. Score columns
    will be partial/zero until the final pass — that's fine, the next run with
    --resume re-uses the scraped_email values which is the expensive part."""
    in_fields = list({k for r in rows for k in r.keys()})
    leading = ["source_id", "name", "city", "address", "google_phone", "google_website",
               "scraped_email", "lead_score", "lead_quality"]
    out_fields = [f for f in leading if any(f in r for r in rows)] + \
                 [f for f in in_fields if f not in leading]
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in out_fields})


def compute_lead_score(row: dict, scraped_email: str | None) -> tuple[int, str]:
    """Return (raw_score 0-11, normalized lead_quality '0-10' bucketed)."""
    score = 0
    if row.get("google_website"):
        score += 3
    if row.get("google_phone"):
        score += 2
    if row.get("google_match_confidence") == "high":
        score += 2
    if scraped_email:
        score += 1
    try:
        rc = int(float(row.get("google_user_ratings") or row.get("review_count") or 0))
    except (ValueError, TypeError):
        rc = 0
    if rc > 0:
        # log10(1) = 0, log10(10) = 1, log10(100) = 2, log10(1000) = 3
        score += min(3, int(math.log10(rc + 1)))
    # Normalize to 0-10
    quality = min(10, round(score * 10 / 11))
    return score, str(quality)


def render_shortlist_html(top_rows: list[dict], city: str, n: int) -> str:
    generated_at = time.strftime("%Y-%m-%d %H:%M")
    rows_html = ""
    for i, r in enumerate(top_rows, 1):
        name = html.escape(r.get("name", ""))
        addr = html.escape(r.get("address") or "")[:100]
        phone = html.escape(r.get("google_phone") or "")
        website = r.get("google_website") or ""
        email = html.escape(r.get("scraped_email") or "")
        score = html.escape(r.get("lead_quality") or "")
        reviews = html.escape(r.get("google_user_ratings") or "")

        from urllib.parse import quote
        atc_url = f"https://adstransparency.google.com/?region=TH"  # paste shop name into search
        atc_search = f"https://www.google.com/search?q=\"{quote(r.get('name',''))}\"+udon+thani"
        gmaps = r.get("google_maps_uri") or f"https://www.google.com/maps/search/{quote(r.get('name','') + ' Udon Thani')}"

        website_link = (f'<a href="{html.escape(website)}" target="_blank" rel="noopener">'
                        f'{html.escape(website[:35])}{"..." if len(website) > 35 else ""}</a>'
                        if website else "&mdash;")

        rows_html += f"""
            <tr>
              <td class="rank">{i}</td>
              <td class="score">{score}</td>
              <td><strong>{name}</strong><div class="addr">{addr}</div></td>
              <td>{phone or '&mdash;'}<div class="dim">{reviews} reviews</div></td>
              <td>{website_link}</td>
              <td>{email or '&mdash;'}</td>
              <td class="links">
                <a href="{atc_url}" target="_blank" rel="noopener" title="Open Transparency Center, then paste shop name in search">Transparency &uarr;</a>
                <a href="{atc_search}" target="_blank" rel="noopener" title="Google Search with shop name">G Search</a>
                <a href="{html.escape(gmaps)}" target="_blank" rel="noopener">Maps</a>
              </td>
            </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<title>{html.escape(city)} &mdash; top {n} ad-check shortlist</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
         max-width: 1280px; margin: 0 auto; padding: 24px; background: #f7f7f8;
         color: #1a1a2e; line-height: 1.5; }}
  .header {{ background: #0d2818; color: #e6f4ec; padding: 24px 28px;
             border-radius: 10px; margin-bottom: 20px; }}
  .header h1 {{ margin: 0 0 6px; color: white; }}
  .header p {{ margin: 0; opacity: 0.85; font-size: 14px; }}
  .instructions {{ background: #eff6ff; border: 1px solid #3b82f6; border-radius: 8px;
                   padding: 14px 18px; margin-bottom: 22px; font-size: 13px;
                   line-height: 1.6; color: #1e3a8a; }}
  .instructions code {{ background: rgba(30,58,138,0.08); padding: 1px 6px; border-radius: 3px; }}
  table {{ width: 100%; border-collapse: collapse; background: white;
           border-radius: 8px; overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,.05);
           font-size: 13px; }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #eaeaea;
            vertical-align: top; }}
  th {{ background: #f3f4f6; font-weight: 600; font-size: 11px;
        text-transform: uppercase; letter-spacing: 0.5px; color: #4b5563; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover {{ background: #fafafa; }}
  td.rank {{ font-weight: 700; color: #94a3b8; }}
  td.score {{ font-weight: 700; color: #15803d; font-size: 16px; }}
  .addr {{ font-size: 11px; color: #64748b; margin-top: 2px; }}
  .dim {{ font-size: 11px; color: #94a3b8; }}
  td.links {{ white-space: nowrap; }}
  td.links a {{ display: inline-block; padding: 3px 8px; border-radius: 4px;
                background: #f3f4f6; color: #15803d; text-decoration: none;
                font-size: 11px; margin-right: 4px; }}
  td.links a:hover {{ background: #dcfce7; }}
  a {{ color: #15803d; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style>
</head><body>
  <div class="header">
    <h1>{html.escape(city)} &mdash; ad-check shortlist (top {n})</h1>
    <p>Ranked by lead-quality score (website + phone + reviews + match confidence + email).
       Use this list to manually verify which shops are running Google Ads.
       Generated {generated_at}.</p>
  </div>

  <div class="instructions">
    <strong>How to use:</strong>
    For each shop:
    (1) Click the <strong>Transparency &uarr;</strong> link &rarr; paste the shop name into the search box on adstransparency.google.com &rarr; note any active or recent ads.
    (2) <strong>G Search</strong> opens Google with the shop name &rarr; look for "Sponsored" or "Ad" labels in results.
    (3) <strong>Maps</strong> opens the location &rarr; note any "Sponsored" pin or local-services indicators.
    <br><br>
    Once you've collected ad-evidence notes, you can edit them into the per-shop Notes field in the main city report (<code>report_udon_thani.html</code>) using the Edit panel.
  </div>

  <table>
    <thead><tr>
      <th>#</th><th>Score</th><th>Shop &amp; Address</th>
      <th>Phone / Reviews</th><th>Website</th><th>Email</th><th>Ad-check links</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("city", nargs="?", default=None,
                        help="City to qualify (e.g. 'Udon Thani'). Omit when using --country.")
    parser.add_argument("--country", action="store_true",
                        help="Run on the full country file (weed_th_google.csv). "
                             "Writes leads_country.csv + per-city shortlists.")
    parser.add_argument("--top", type=int, default=30, help="Shortlist size (default 30)")
    parser.add_argument("--skip-emails", action="store_true",
                        help="Skip the email-scraping pass (only compute scores)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip rows whose scraped_email is already known in the existing output. "
                             "Use to recover from a crash without re-fetching.")
    args = parser.parse_args()

    if not args.country and not args.city:
        parser.error("Provide a city name or --country")
    if args.country and args.city:
        parser.error("Pass either a city OR --country, not both")

    city_label = "country" if args.country else args.city
    rows, source = load_input(None if args.country else args.city)
    print(f"[leads] mode={city_label!r}  source={source}  rows={len(rows):,}")

    safe = "country" if args.country else args.city.lower().replace(" ", "_")
    out_csv = os.path.join(DATA_DIR, f"leads_{safe}.csv")

    # Resume: read existing output and seed scraped_email values from it
    existing_emails: dict[str, str] = {}
    if args.resume and os.path.exists(out_csv):
        with open(out_csv, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("source_id"):
                    existing_emails[r["source_id"]] = r.get("scraped_email", "")
        print(f"[leads] resume: seeded {len(existing_emails):,} rows from previous {out_csv}")
        for r in rows:
            if r.get("source_id") in existing_emails:
                r["scraped_email"] = existing_emails[r["source_id"]]

    # Email-scrape pass — skip social URLs (they don't expose emails) and rows
    # already resumed. Stream-write progress every 50 rows so a crash mid-run
    # never loses prior work.
    new_email_rows = 0
    if not args.skip_emails:
        candidates = [
            r for r in rows
            if r.get("google_website")
            and not is_social_url(r["google_website"])
            and r.get("source_id") not in existing_emails
        ]
        total_with_websites = sum(1 for r in rows if r.get("google_website"))
        social_count = sum(1 for r in rows if r.get("google_website") and is_social_url(r["google_website"]))
        print(f"[leads] websites total: {total_with_websites:,} | social (skipped): {social_count:,} "
              f"| to fetch: {len(candidates):,}")
        est_min = len(candidates) * (FETCH_DELAY + 4) / 60
        print(f"[leads] estimated fetch time: ~{est_min:.0f} min (delay {FETCH_DELAY}s + ~4s avg fetch)")

        progress_every = 50
        for i, r in enumerate(candidates, 1):
            url = r.get("google_website", "").strip()
            if i > 1:
                time.sleep(FETCH_DELAY)
            html_text = fetch_homepage(url)
            if not html_text:
                r["scraped_email"] = ""
                if i % 10 == 0 or i == len(candidates):
                    print(f"  [{i:>5}/{len(candidates)}] {r.get('name','')[:30]:30s} | fetch failed")
                continue
            emails = extract_emails(html_text)
            r["scraped_email"] = emails[0] if emails else ""
            if emails:
                new_email_rows += 1
                print(f"  [{i:>5}/{len(candidates)}] {r.get('name','')[:30]:30s} | EMAIL: {emails[0]}")
            elif i % 25 == 0 or i == len(candidates):
                print(f"  [{i:>5}/{len(candidates)}] ... ({new_email_rows} emails found so far)")

            # Crash-safety: flush partial results periodically
            if i % progress_every == 0:
                _flush_partial(rows, out_csv)

        # All rows that didn't get scraped get empty email (including social URLs)
        for r in rows:
            r.setdefault("scraped_email", "")
        denom = max(1, total_with_websites - social_count)
        print(f"[leads] emails found: {new_email_rows}/{len(candidates)} "
              f"({100*new_email_rows/max(1,len(candidates)):.0f}% of fetched, "
              f"{100*new_email_rows/denom:.0f}% of non-social sites)")
    else:
        for r in rows:
            r.setdefault("scraped_email", "")

    # Score pass
    for r in rows:
        raw, quality = compute_lead_score(r, r.get("scraped_email"))
        r["lead_score"] = str(raw)
        r["lead_quality"] = quality

    # Sort by lead score descending
    rows.sort(key=lambda r: -int(r.get("lead_score") or 0))

    # Final write (full state with scores)
    _flush_partial(rows, out_csv)
    print(f"\n[leads] wrote {out_csv} ({len(rows):,} rows)")

    # Top-N shortlist HTML
    top = rows[: args.top]
    label = "Thailand (country-wide)" if args.country else args.city
    html_text = render_shortlist_html(top, label, args.top)
    out_html = os.path.join(DATA_DIR, f"top{args.top}_adcheck_{safe}.html")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html_text)
    print(f"[leads] wrote {out_html} (top {len(top)})")

    # Summary
    print("\n[leads] score distribution:")
    from collections import Counter
    dist = Counter(int(r.get("lead_score") or 0) for r in rows)
    for s in sorted(dist.keys(), reverse=True):
        bar = "#" * dist[s]
        print(f"  raw {s:2d}: {dist[s]:3d}  {bar[:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
