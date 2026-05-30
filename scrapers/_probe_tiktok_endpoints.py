"""Probe likely TikTok Ad Library endpoint patterns."""

import json
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0 Safari/537.36"

BASE = "https://library.tiktok.com/api/v1"
HEADERS_GET = {
    "User-Agent": UA, "Accept": "application/json, text/plain, */*",
    "Referer": "https://library.tiktok.com/ads?region=TH",
}
HEADERS_POST = {**HEADERS_GET, "Content-Type": "application/json"}

# Try suggestion with various queries + suggest_type values
print("=== suggestion endpoint, various suggest_type values ===")
for st in ("1", "2", "3"):
    for q in ("Bumrungrad", "Lazada", "AIS", "Coca-Cola", "Toyota"):
        body = {"query": q, "limit": 20, "suggest_type": st}
        r = requests.post(f"{BASE}/suggestion", headers=HEADERS_POST,
                          data=json.dumps(body), timeout=10)
        if r.status_code == 200 and r.text:
            d = r.json() if r.text.startswith("{") else {}
            adv = d.get("data", {}).get("adv_names", []) or d.get("data", {}).get("ad_keywords", [])
            print(f"  st={st}  q={q!r:<18}  len={len(r.text):>4}  adv_count={len(adv) if isinstance(adv, list) else '?'}")
            if adv and isinstance(adv, list):
                for a in adv[:3]:
                    print(f"      - {str(a)[:80]}")
        else:
            print(f"  st={st}  q={q!r}  HTTP {r.status_code}")

# Try guessed search/list endpoints
print("\n=== guessed search/list endpoints ===")
for method, path, payload in [
    ("GET",  "/ads?country=TH&query=Bumrungrad", None),
    ("GET",  "/ads/all?country=TH&keyword=Bumrungrad", None),
    ("GET",  "/ads/search?country=TH&query=Bumrungrad", None),
    ("POST", "/ads/search", {"query": "Bumrungrad", "country": "TH", "limit": 20}),
    ("POST", "/search", {"query": "Bumrungrad", "country": "TH", "limit": 20}),
    ("POST", "/ads", {"query": "Bumrungrad", "country": "TH", "limit": 20}),
    ("POST", "/advertiser/search", {"query": "Bumrungrad", "country": "TH"}),
    ("POST", "/advertisers", {"query": "Bumrungrad", "country": "TH"}),
    ("GET",  "/advertisers?country=TH&keyword=Bumrungrad", None),
]:
    url = BASE + path
    try:
        if method == "GET":
            r = requests.get(url, headers=HEADERS_GET, timeout=10)
        else:
            r = requests.post(url, headers=HEADERS_POST, data=json.dumps(payload), timeout=10)
        ct = r.headers.get("content-type", "")
        print(f"  {method:<4} {r.status_code}  len={len(r.text):>5}  {path}")
        if r.status_code == 200 and len(r.text) < 400:
            print(f"      body: {r.text[:300]}")
        elif r.status_code == 200 and "json" in ct:
            # Could be the search endpoint! Show structure
            print(f"      JSON preview: {r.text[:300]}")
    except Exception as e:
        print(f"  {method:<4} ERR  {path}: {e}")
