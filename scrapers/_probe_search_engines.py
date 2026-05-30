"""Test which public search engine lets us scrape unauth'd."""

import re
import requests
import time
from urllib.parse import quote

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/148.0 Safari/537.36")

# For the FB page lookup pattern: "<shop>" site:facebook.com
QUERIES = [
    '"GODFATHER UDON" site:facebook.com',
    '"Shelly Cafe" site:facebook.com',
    '"เฮียอั๋นต้มเลือดหมู" site:facebook.com',
]

ENGINES = [
    ("Bing",         "https://www.bing.com/search?q={q}"),
    ("Brave",        "https://search.brave.com/search?q={q}"),
    ("Mojeek",       "https://www.mojeek.com/search?q={q}"),
    ("Startpage",    "https://www.startpage.com/sp/search?query={q}"),
    ("DDG html",     "https://html.duckduckgo.com/html/?q={q}"),
    ("Yandex",       "https://yandex.com/search/?text={q}"),
]

for engine_name, tmpl in ENGINES:
    print(f"\n=== {engine_name} ===")
    for q in QUERIES[:1]:  # just first query to save time
        url = tmpl.format(q=quote(q))
        try:
            r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
                             timeout=10, allow_redirects=True)
        except Exception as e:
            print(f"  ERR {q}: {e}")
            continue
        body = r.text or ""
        title_m = re.search(r"<title[^>]*>([^<]+)</title>", body, re.I)
        title = title_m.group(1)[:60] if title_m else ""
        # Count facebook.com links in result
        fb_links = re.findall(r'https?://(?:www\.|m\.|web\.)?facebook\.com/[^\s"\'<>]+', body)
        fb_links = [l for l in fb_links if "/ads/" not in l and "/policies" not in l
                    and "/legal" not in l and "/help" not in l][:5]
        # Detect captcha / blocks
        captcha = ("captcha" in body.lower() or "are you human" in body.lower()
                   or "cf-chl" in body.lower())
        print(f"  {r.status_code}  len={len(body):>6}  {q[:35]:<35}  fb_links={len(fb_links)}"
              f"{' [CAPTCHA]' if captcha else ''}")
        if title:
            print(f"      title: {title}")
        for l in fb_links[:3]:
            print(f"      -> {l[:80]}")
        time.sleep(2)  # polite
