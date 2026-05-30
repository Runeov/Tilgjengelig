"""Find each shop's Facebook page URL by searching Brave for the shop name.

Why Brave: FB itself returns HTTP 400 for any unauth'd page fetch. Google
and Bing block automated search. DuckDuckGo, Yandex, Startpage all
captcha-wall. Brave Search returns full results to standard requests.

Approach (per shop):
  GET https://search.brave.com/search?q="<shop name>"+site:facebook.com
  parse first facebook.com link from results → that's the candidate FB page

This catches whether the shop HAS a Facebook page indexed by Brave. We can't
tell activity (recent posts) without rendering FB itself, but presence-of-page
is itself a B2B signal: shops with no findable FB page are usually
informal/inactive operators.

Outputs per row:
  fb_page_url           top facebook.com URL Brave returned (cleaned)
  fb_page_results_count number of distinct fb URLs in top results
  fb_page_check_status  ok | empty | http_error | parse_error

Usage:
  python check_fb_pages.py udonthani --limit 30      # sanity
  python check_fb_pages.py udonthani --food-only     # restrict
  python check_fb_pages.py udonthani --resume        # continue after crash
"""

import argparse
import csv
import os
import re
import sys
import time
from urllib.parse import quote, urlparse

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/148.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
}

# Per-shop pacing. Brave isn't as bot-paranoid as Google but still has limits.
REQUEST_DELAY = 2.5

# Skip these FB URL patterns — not actual business pages
JUNK_FB_PATHS = (
    "/login", "/signup", "/policies", "/legal", "/help", "/business/help",
    "/groups/", "/ads/library", "/marketplace", "/watch",
)

NEW_FIELDS = ["fb_page_url", "fb_page_results_count", "fb_page_check_status"]


def search_brave(query: str) -> str | None:
    url = f"https://search.brave.com/search?q={quote(query)}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    return r.text


def extract_fb_urls(html: str) -> list[str]:
    """Pull facebook.com URLs from Brave's results HTML, filter junk, dedupe."""
    raw = re.findall(r'https?://(?:www\.|m\.|web\.)?facebook\.com/[^\s"\'<>]+', html or "")
    out = []
    seen = set()
    for u in raw:
        # Cleanup trailing chars
        u = u.rstrip(".,;)]")
        # Skip junk paths
        if any(jp in u.lower() for jp in JUNK_FB_PATHS):
            continue
        # Canonicalize: strip query string + fragment, force www
        p = urlparse(u)
        path = p.path
        # Skip if path is just "/" or empty
        if path in ("", "/"):
            continue
        canon = f"https://www.facebook.com{path}"
        if canon in seen:
            continue
        seen.add(canon)
        out.append(canon)
    return out


def check_one(shop_name: str) -> dict:
    out = {f: "" for f in NEW_FIELDS}
    query = f'"{shop_name}" site:facebook.com'
    html = search_brave(query)
    if html is None:
        out["fb_page_check_status"] = "http_error"
        return out
    urls = extract_fb_urls(html)
    if not urls:
        out["fb_page_check_status"] = "empty"
        out["fb_page_results_count"] = "0"
        return out
    out["fb_page_url"] = urls[0]
    out["fb_page_results_count"] = str(len(urls))
    out["fb_page_check_status"] = "ok"
    return out


def load_already_done(out_path: str) -> set:
    done: set = set()
    if not os.path.exists(out_path):
        return done
    with open(out_path, "r", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            sid = r.get("publicId") or r.get("id")
            if sid and r.get("fb_page_check_status"):
                done.add(sid)
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slug", help="Region slug matching input CSV (e.g. 'udonthani')")
    parser.add_argument("--limit", type=int, default=None, help="Only check N shops")
    parser.add_argument("--food-only", action="store_true", help="Skip non-food rows")
    parser.add_argument("--resume", action="store_true", help="Skip rows already checked")
    args = parser.parse_args()

    in_path = os.path.join(DATA_DIR, f"wongnai_{args.slug}.csv")
    out_path = os.path.join(DATA_DIR, f"fb_pages_{args.slug}.csv")
    if not os.path.exists(in_path):
        raise SystemExit(f"Input not found: {in_path}. Run scrape_wongnai.py {args.slug} first.")

    with open(in_path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"[fb_pages] input: {len(rows):,} rows")
    if args.food_only:
        rows = [r for r in rows if r.get("is_likely_food") == "1"]
        print(f"[fb_pages] --food-only: {len(rows):,} food rows")

    in_fields = list(rows[0].keys()) if rows else []
    out_fields = in_fields + [f for f in NEW_FIELDS if f not in in_fields]

    already = load_already_done(out_path) if args.resume else set()
    if already:
        print(f"[fb_pages] resume: {len(already)} rows already checked")
    to_do = [r for r in rows if (r.get("publicId") or r.get("id")) not in already]
    if args.limit:
        to_do = to_do[: args.limit]
    est_min = len(to_do) * REQUEST_DELAY / 60
    print(f"[fb_pages] to check: {len(to_do)} (est ~{est_min:.0f} min @ {REQUEST_DELAY}s/req)")

    file_exists = os.path.exists(out_path)
    mode = "a" if (args.resume and file_exists) else "w"
    out_f = open(out_path, mode, encoding="utf-8", newline="")
    writer = csv.DictWriter(out_f, fieldnames=out_fields)
    if mode == "w":
        writer.writeheader()
        out_f.flush()

    hits = zeros = errors = 0
    try:
        for i, row in enumerate(to_do, 1):
            name = (row.get("displayName") or row.get("name_english")
                    or row.get("name_thai") or "").strip()
            if not name:
                row.update({f: "" for f in NEW_FIELDS})
                row["fb_page_check_status"] = "no_name"
                writer.writerow({k: row.get(k, "") for k in out_fields})
                out_f.flush()
                continue
            if i > 1:
                time.sleep(REQUEST_DELAY)
            fields = check_one(name)
            row.update(fields)
            writer.writerow({k: row.get(k, "") for k in out_fields})
            out_f.flush()
            status = fields["fb_page_check_status"]
            if status == "ok":
                hits += 1
            elif status == "empty":
                zeros += 1
            else:
                errors += 1
            if i % 5 == 0 or i == len(to_do):
                fb_short = (fields.get("fb_page_url") or "").replace("https://www.facebook.com", "fb.com")[:40]
                print(f"  [{i:>4}/{len(to_do)}] {name[:25]:<25} | {status:<12} | {fb_short}")
    finally:
        out_f.close()

    print(f"\n[fb_pages] done. hits={hits} zeros={zeros} errors={errors}")
    print(f"[fb_pages] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
