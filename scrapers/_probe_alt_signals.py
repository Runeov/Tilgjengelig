"""Probe 3 alternative B2B/ad-spend signals for hospitality vertical:

1. TikTok Ad Library (library.tiktok.com)
2. TripAdvisor Udon Thani restaurant listings
3. LINE Official Account discoverability via Google search

Goal per source:
  - Is it scrapable from this machine?
  - What URL/API pattern works?
  - What signal does it give us for Thai SMB hospitality?
"""

import json
import re
import sys
import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0 Safari/537.36"

# Test queries: mix of confirmed advertisers + Udon Thani shop names
TEST_BRANDS = ["Café Amazon", "Bumrungrad", "Lazada"]
TEST_UDON_SHOPS = ["GODFATHER UDON", "Shelly Cafe", "เฮียอั๋นต้มเลือดหมู"]


print("=" * 70)
print("1) TIKTOK AD LIBRARY")
print("=" * 70)
# TikTok's transparency surface is library.tiktok.com or "tiktok.com/business/library"
# Quick probe of the homepage + common search URL patterns.
candidates = [
    "https://library.tiktok.com/",
    "https://library.tiktok.com/ads",
    "https://library.tiktok.com/ads?region=TH",
    "https://library.tiktok.com/ads?country=TH",
    "https://library.tiktok.com/search?q=Bumrungrad&region=TH",
    "https://library.tiktok.com/ads?adv_name=Bumrungrad",
    "https://library.tiktok.com/api/v1/ads/all/?country=TH&keyword=Bumrungrad",
]
for url in candidates:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=8, allow_redirects=False)
        title = ""
        if r.status_code == 200 and r.text:
            m = re.search(r"<title>([^<]+)</title>", r.text, re.I)
            if m:
                title = m.group(1)[:60]
        print(f"  {r.status_code}  len={len(r.text):>6}  {url}")
        if title:
            print(f"        title: {title}")
        if r.status_code in (301, 302, 303, 307, 308):
            print(f"        redirects to: {r.headers.get('Location', '')[:100]}")
    except Exception as e:
        print(f"  ERR  {url} -> {e}")

print("\n" + "=" * 70)
print("2) TRIPADVISOR — Udon Thani restaurants")
print("=" * 70)
# TripAdvisor is famously anti-bot. Probe carefully.
candidates = [
    "https://www.tripadvisor.com/Restaurants-g297921-Udon_Thani_Udon_Thani_Province.html",
    "https://www.tripadvisor.com/Restaurants-g297921.html",
    "https://www.tripadvisor.com/Tourism-g297921-Udon_Thani_Udon_Thani_Province-Vacations.html",
    "https://www.tripadvisor.com/RestaurantSearch?Action=PAGE&geo=297921&itags=10591&sortOrder=popularity",
]
for url in candidates:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=10, allow_redirects=False)
        title = ""
        cf = ""
        if r.text:
            m = re.search(r"<title>([^<]+)</title>", r.text, re.I)
            if m:
                title = m.group(1)[:80]
            if "cf-chl" in r.text.lower() or "just a moment" in r.text.lower():
                cf = " [CLOUDFLARE CHALLENGE]"
        print(f"  {r.status_code}  len={len(r.text):>6}  {url}{cf}")
        if title:
            print(f"        title: {title}")
    except Exception as e:
        print(f"  ERR  {url} -> {e}")

print("\n" + "=" * 70)
print("3) LINE OA DETECTION via Google site:lin.ee search")
print("=" * 70)
# Idea: for each shop, query Google for `"<shop name>" site:lin.ee OR site:line.me`
# If results > 0, shop has a LINE OA.
# Use DuckDuckGo HTML (no API key, fewer captcha walls than Google for scraping).
for q in TEST_UDON_SHOPS:
    full_q = f'"{q}" (site:lin.ee OR site:line.me)'
    url = f"https://html.duckduckgo.com/html/?q={quote(full_q)}"
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=12)
        if r.status_code != 200:
            print(f"  {q!r}: HTTP {r.status_code}")
            continue
        # Count result anchors
        soup = BeautifulSoup(r.text, "lxml")
        results = soup.find_all("a", class_="result__a")
        # Filter to actual lin.ee / line.me links
        line_hits = [a for a in results if any(s in (a.get("href", "") or "")
                                                for s in ("lin.ee", "line.me"))]
        print(f"  {q!r}:")
        print(f"     total search results: {len(results)}")
        print(f"     LINE-link hits: {len(line_hits)}")
        for a in line_hits[:3]:
            print(f"       - {a.get('href', '')[:80]}")
        time.sleep(2)  # polite to DDG
    except Exception as e:
        print(f"  {q!r}: ERR {e}")
