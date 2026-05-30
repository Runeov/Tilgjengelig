"""Probe FB page accessibility without login.

We want to detect: 'Does shop X have a FB page? Is it active?'

Three sub-problems:
  A) URL discovery — how do we find the shop's FB slug?
  B) Public access — what FB URLs return useful data without login?
  C) Activity signal — can we tell if the page is recently active?
"""

import re
import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/148.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9,th;q=0.8"}

# A few known public FB URLs to test (known Thai brands)
KNOWN_PAGES = [
    "cafeamazonofficial",   # known Café Amazon brand FB page
    "Bumrungrad",            # known Bumrungrad page
    "LazadaTH",              # known Lazada Thailand page
    "starbucksthailand",     # known Starbucks TH
    "nonexistent_test_page_xyz_12345",  # control: should not exist
]

print("=== A) WHAT FB URLs RETURN WITHOUT LOGIN ===\n")
for slug in KNOWN_PAGES:
    for base in ("https://www.facebook.com", "https://m.facebook.com"):
        url = f"{base}/{slug}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=False)
        except Exception as e:
            print(f"  ERR {url}: {e}")
            continue
        body = r.text or ""
        login_wall = "login" in body.lower() and "facebook" in body.lower() and len(body) < 50000
        not_found = "page not found" in body.lower() or "isn't available" in body.lower()
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", body, re.I)
        title = title_match.group(1)[:60] if title_match else ""
        marker = ""
        if r.status_code in (301, 302, 303, 307, 308):
            marker = f" -> {r.headers.get('Location', '')[:80]}"
        elif login_wall:
            marker = " [LOGIN WALL]"
        elif not_found:
            marker = " [NOT FOUND]"
        print(f"  {r.status_code}  len={len(body):>6}  {url}{marker}")
        if title:
            print(f"      title: {title}")
        # Sniff for follower/like counts (public metrics often appear even on login wall)
        for kw_re in [r"(\d[\d,.]*)\s*(likes|followers|ผู้ติดตาม|คนถูกใจ)"]:
            for m in re.finditer(kw_re, body, re.I)[:3] if False else re.findall(kw_re, body, re.I)[:3]:
                print(f"      metric: {m}")
        # Probe for og:description or meta description
        og_desc = re.search(r'<meta[^>]*property="og:description"[^>]*content="([^"]+)"', body)
        if og_desc:
            print(f"      og:description: {og_desc.group(1)[:120]}")
