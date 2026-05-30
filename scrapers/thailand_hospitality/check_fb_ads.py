"""Check Facebook Ad Library for each shop in a Wongnai CSV to detect whether
the shop is an active or recent advertiser on Facebook.

Approach: for each shop, navigate Playwright to
  https://www.facebook.com/ads/library/?country=TH&q=<shop name>&active_status=all&ad_type=all&search_type=keyword_unordered
and parse the result count from the rendered page. A non-zero count means at
least one FB ad in Thailand mentions the shop name — usually but not always
the shop itself (false positives possible for generic names).

Output adds per-row:
  fb_ad_count       — number of ads found (0 if none, '?' if can't parse)
  has_fb_ads        — '1' if count > 0, '0' if count == 0, '' otherwise
  fb_search_url     — the URL we hit (for manual verification)
  atc_search_url    — link to Google Ads Transparency Center search (manual check)
  fb_check_status   — ok | timeout | error:<...>

Usage:
  python check_fb_ads.py udonthani --limit 5      # sanity
  python check_fb_ads.py udonthani --food-only    # only food/drink rows
  python check_fb_ads.py udonthani --resume       # continue after a crash
"""

import argparse
import csv
import os
import re
import sys
import time
from urllib.parse import quote

from playwright.sync_api import sync_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

# Per-shop pacing. FB tolerates better than Wongnai; 3s is comfortable.
CRAWL_DELAY = 3.0
NAV_TIMEOUT = 25000  # ms

NEW_FIELDS = [
    "fb_ad_count", "has_fb_ads", "fb_search_url", "atc_search_url", "fb_check_status",
]


def build_fb_url(name: str) -> str:
    # `keyword_exact_phrase` reduces false positives dramatically vs `keyword_unordered`
    # (e.g. generic Thai dish names that match many unrelated ads).
    return (
        "https://www.facebook.com/ads/library/"
        f"?active_status=all&ad_type=all&country=TH"
        f"&q={quote(name)}&search_type=keyword_exact_phrase"
    )


def build_atc_url(name: str) -> str:
    return f"https://adstransparency.google.com/?region=TH&q={quote(name)}"


# Parsing helpers — FB shows result count like "~5,000 results" or "1 result"
# or "0 results" or "ผลการค้นหา 5 รายการ" (Thai).
# We grep liberally and pick the largest number near "result" / "รายการ".
_PAT_EN = re.compile(r"(?:[~~約]?)\s*([\d,]+)\+?\s+result", re.I)
_PAT_TH = re.compile(r"([\d,]+)\s*(?:รายการ|ผล)")


def parse_result_count(body_text: str) -> int | None:
    nums = []
    for m in _PAT_EN.finditer(body_text):
        try:
            nums.append(int(m.group(1).replace(",", "")))
        except ValueError:
            pass
    for m in _PAT_TH.finditer(body_text):
        try:
            nums.append(int(m.group(1).replace(",", "")))
        except ValueError:
            pass
    if not nums:
        if any(s in body_text.lower() for s in ("no ads", "no results")):
            return 0
        return None
    # If multiple numbers, take the max (FB occasionally has "0 results found" + a counter)
    return max(nums)


def check_one(page, name: str) -> dict:
    """Open FB Ad Library for one shop, return parsed fields."""
    url = build_fb_url(name)
    out = {
        "fb_search_url": url,
        "atc_search_url": build_atc_url(name),
        "fb_ad_count": "",
        "has_fb_ads": "",
        "fb_check_status": "",
    }
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
        page.wait_for_timeout(3500)  # let results render
        body = page.inner_text("body", timeout=4000)
    except Exception as e:
        out["fb_check_status"] = f"error:{type(e).__name__}"
        return out
    n = parse_result_count(body or "")
    if n is None:
        out["fb_check_status"] = "unparsed"
        return out
    out["fb_ad_count"] = str(n)
    out["has_fb_ads"] = "1" if n > 0 else "0"
    out["fb_check_status"] = "ok"
    return out


def load_already_done(out_path: str) -> set:
    done: set = set()
    if not os.path.exists(out_path):
        return done
    with open(out_path, "r", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            sid = r.get("publicId") or r.get("id")
            if sid and r.get("fb_check_status") in ("ok", "unparsed"):
                done.add(sid)
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slug", help="Region slug matching the input CSV (e.g. 'udonthani')")
    parser.add_argument("--limit", type=int, default=None, help="Only check N shops (sanity-test)")
    parser.add_argument("--food-only", action="store_true",
                        help="Skip rows where is_likely_food=0")
    parser.add_argument("--resume", action="store_true",
                        help="Skip rows that already have fb_check_status set")
    args = parser.parse_args()

    in_path = os.path.join(DATA_DIR, f"wongnai_{args.slug}.csv")
    out_path = os.path.join(DATA_DIR, f"fb_ads_{args.slug}.csv")
    if not os.path.exists(in_path):
        raise SystemExit(f"Input not found: {in_path}. Run scrape_wongnai.py {args.slug} first.")

    with open(in_path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"[fb_ads] input: {len(rows):,} rows from {in_path}")
    if args.food_only:
        rows = [r for r in rows if r.get("is_likely_food") == "1"]
        print(f"[fb_ads] --food-only: {len(rows):,} food rows")

    in_fields = list(rows[0].keys()) if rows else []
    out_fields = in_fields + [f for f in NEW_FIELDS if f not in in_fields]
    already = load_already_done(out_path) if args.resume else set()
    if already:
        print(f"[fb_ads] resume: {len(already)} rows already checked")

    to_do = [r for r in rows if (r.get("publicId") or r.get("id")) not in already]
    if args.limit:
        to_do = to_do[: args.limit]
    print(f"[fb_ads] to check: {len(to_do)} (est runtime ~{len(to_do) * (CRAWL_DELAY + 4) / 60:.0f} min)")

    file_exists = os.path.exists(out_path)
    mode = "a" if (args.resume and file_exists) else "w"
    out_f = open(out_path, mode, encoding="utf-8", newline="")
    writer = csv.DictWriter(out_f, fieldnames=out_fields)
    if mode == "w":
        writer.writeheader()
        out_f.flush()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/148.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = context.new_page()

        hits = 0
        zeros = 0
        unparsed = 0
        errors = 0
        try:
            for i, row in enumerate(to_do, 1):
                name = (row.get("displayName") or row.get("name_english")
                        or row.get("name_thai") or "").strip()
                if not name:
                    row.update({f: "" for f in NEW_FIELDS})
                    row["fb_check_status"] = "no_name"
                    writer.writerow({k: row.get(k, "") for k in out_fields})
                    out_f.flush()
                    continue
                if i > 1:
                    time.sleep(CRAWL_DELAY)
                fields = check_one(page, name)
                row.update(fields)
                writer.writerow({k: row.get(k, "") for k in out_fields})
                out_f.flush()
                cnt = fields["fb_ad_count"]
                if fields["fb_check_status"] == "ok" and int(cnt or 0) > 0:
                    hits += 1
                elif fields["fb_check_status"] == "ok":
                    zeros += 1
                elif fields["fb_check_status"] == "unparsed":
                    unparsed += 1
                else:
                    errors += 1
                if i % 5 == 0 or i == len(to_do):
                    print(f"  [{i:>4}/{len(to_do)}] {name[:30]:<30} | "
                          f"count={cnt or '-':<6} status={fields['fb_check_status']}")
        finally:
            browser.close()
            out_f.close()

    print(f"\n[fb_ads] done. hits={hits} zeros={zeros} unparsed={unparsed} errors={errors}")
    print(f"[fb_ads] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
