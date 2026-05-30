"""For each hospitality row with a real (non-social) website, fetch the
homepage and extract email addresses. Output:
  data/emails_country.csv  — shop name + scraped emails + source URL

Then a post-step re-merges and re-aggregates so country reports get the
new emails.

Approach reused from cannabis lead_qualify.py.
"""

import argparse
import csv
import os
import re
import sys
import time
from urllib.parse import urlparse

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

JUNK_LOCAL = {"noreply", "no-reply", "do-not-reply", "privacy", "webmaster",
              "abuse", "postmaster"}
JUNK_SUFFIX = ("example.com", "test.com", "wixpress.com", "sentry.io")

# Same social-host blocklist used by merge_hospitality.is_real_website
SOCIAL_HOSTS = {
    "facebook.com", "m.facebook.com", "fb.me",
    "instagram.com", "instagr.am",
    "line.me", "lin.ee", "linktr.ee", "beacons.ai", "bio.link",
    "heylink.me", "taplink.cc", "url.in.th",
    "tiktok.com", "twitter.com", "x.com", "youtube.com", "youtu.be",
    "t.me",
}

FETCH_TIMEOUT = 6
DELAY = 0.5  # between site fetches


def is_real_website(url: str) -> bool:
    if not url or not url.startswith(("http://", "https://")):
        return False
    try:
        host = (urlparse(url).hostname or "").lower().lstrip(".")
    except Exception:
        return False
    if host.startswith("www."):
        host = host[4:]
    return bool(host) and host not in SOCIAL_HOSTS


def looks_like_real_email(addr: str) -> bool:
    local, _, domain = addr.partition("@")
    if not local or not domain:
        return False
    if local.lower() in JUNK_LOCAL:
        return False
    if any(domain.lower().endswith(s) for s in JUNK_SUFFIX):
        return False
    if re.search(r"\.(png|jpg|jpeg|gif|svg|webp|woff|css|js)$", addr, re.I):
        return False
    return True


def extract_emails(html_text: str) -> list[str]:
    found, seen = [], set()
    for m in re.finditer(r'href=["\']mailto:([^"\'?]+)', html_text, re.I):
        e = m.group(1).strip()
        if e.lower() not in seen and looks_like_real_email(e):
            seen.add(e.lower()); found.append(e)
    try:
        soup = BeautifulSoup(html_text, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ")
    except Exception:
        text = html_text
    for m in EMAIL_RE.finditer(text):
        e = m.group(0).strip(".,;:")
        if e.lower() not in seen and looks_like_real_email(e):
            seen.add(e.lower()); found.append(e)
    return found


def fetch_html(url: str) -> str | None:
    try:
        r = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/148.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
        }, timeout=FETCH_TIMEOUT, verify=False, allow_redirects=True)
        if r.status_code == 200 and "html" in r.headers.get("content-type", "").lower():
            return r.text
    except Exception:
        return None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", default=os.path.join(DATA_DIR, "hospitality_country.csv"),
                        help="Input CSV (default: hospitality_country.csv)")
    parser.add_argument("--output", default=os.path.join(DATA_DIR, "emails_country.csv"))
    parser.add_argument("--resume", action="store_true",
                        help="Skip rows already in output")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        raise SystemExit(f"Not found: {args.input}")

    with open(args.input, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"[emails] input {len(rows):,} rows")

    candidates = [r for r in rows if is_real_website(r.get("website") or "")]
    print(f"[emails] {len(candidates):,} rows have real (non-social) websites")

    already_done: set = set()
    if args.resume and os.path.exists(args.output):
        with open(args.output, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("src_id"):
                    already_done.add(r["src_id"])
        print(f"[emails] resume: {len(already_done)} already done, skipping")
        candidates = [r for r in candidates if r.get("src_id") not in already_done]

    est_min = len(candidates) * (DELAY + 4) / 60
    print(f"[emails] to fetch: {len(candidates)} (est ~{est_min:.0f} min)")

    fieldnames = ["src_id", "name", "city", "website", "scraped_emails", "fetch_status"]
    mode = "a" if (args.resume and os.path.exists(args.output)) else "w"
    out_f = open(args.output, mode, encoding="utf-8", newline="")
    writer = csv.DictWriter(out_f, fieldnames=fieldnames)
    if mode == "w":
        writer.writeheader()
        out_f.flush()

    hits = 0
    try:
        for i, r in enumerate(candidates, 1):
            if i > 1:
                time.sleep(DELAY)
            url = (r.get("website") or "").strip()
            html_text = fetch_html(url)
            if not html_text:
                out = {"src_id": r.get("src_id", ""),
                       "name": r.get("name", ""),
                       "city": r.get("_city_slug") or r.get("city", ""),
                       "website": url,
                       "scraped_emails": "",
                       "fetch_status": "fetch_failed"}
            else:
                emails = extract_emails(html_text)
                if emails:
                    hits += 1
                out = {"src_id": r.get("src_id", ""),
                       "name": r.get("name", ""),
                       "city": r.get("_city_slug") or r.get("city", ""),
                       "website": url,
                       "scraped_emails": "; ".join(emails),
                       "fetch_status": "ok"}
            writer.writerow(out)
            out_f.flush()
            if i % 20 == 0 or i == len(candidates):
                print(f"  [{i:>4}/{len(candidates)}] {(r.get('name','')[:30]):<30} | "
                      f"emails={len(out['scraped_emails'].split('; ')) if out['scraped_emails'] else 0}  "
                      f"(hits so far: {hits})")
    finally:
        out_f.close()

    print(f"\n[emails] done. emails found in {hits}/{len(candidates)} sites.")
    print(f"[emails] wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
