"""Crack TikTok Ad Library's search RPC. Same approach as ATC:
  1. Headed browser, navigate to library.tiktok.com/ads
  2. Wait for JS hydration
  3. Find search input, fill, watch XHR
  4. Capture the RPC URL + payload
"""

import json
import sys
import time

from playwright.sync_api import sync_playwright

TEST_QUERY = "Bumrungrad"  # known Thai-major-advertiser; high chance of TikTok ads too


def main() -> int:
    captured: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/148.0 Safari/537.36",
            viewport={"width": 1400, "height": 900},
            locale="en-US",
        )
        page = context.new_page()

        def on_request(req):
            if req.resource_type not in ("xhr", "fetch"):
                return
            url = req.url
            if any(s in url for s in ("googletag", "/log?", "analytics", "telemetry")):
                return
            if not ("/api" in url or "ad" in url.lower() or "search" in url.lower()
                    or "rpc" in url.lower() or "advertiser" in url.lower()):
                return
            captured.append({
                "method": req.method, "url": url, "post_data": req.post_data or "",
                "_response": None, "_body": None,
            })

        def on_response(resp):
            for r in captured:
                if r["url"] == resp.url and r["_response"] is None:
                    r["_response"] = resp.status
                    try:
                        r["_body"] = resp.text()[:1500]
                    except Exception:
                        r["_body"] = "<unreadable>"
                    return

        page.on("request", on_request)
        page.on("response", on_response)

        url = "https://library.tiktok.com/ads?region=TH"
        print(f"[probe] navigating {url}")
        try:
            page.goto(url, wait_until="networkidle", timeout=45000)
        except Exception as e:
            print(f"  nav error: {e}")
        page.wait_for_timeout(6000)

        # Find inputs
        inputs = page.evaluate("""
            () => Array.from(document.querySelectorAll(
                'input, textarea, [contenteditable=true], [role=searchbox], [role=combobox]'
            )).map(el => ({
                tag: el.tagName, type: el.type || null,
                placeholder: el.placeholder || el.getAttribute('placeholder'),
                ariaLabel: el.getAttribute('aria-label'),
                visible: el.offsetParent !== null,
                disabled: el.disabled,
                cls: (typeof el.className === 'string' ? el.className.slice(0, 60) : ''),
            }))
        """)
        print(f"[probe] {len(inputs)} input/text elements found:")
        for i, x in enumerate(inputs[:8]):
            print(f"  input[{i}]: {x}")

        # Try filling the most likely search input
        before_count = len(captured)
        filled = False
        for sel in ("input[type='search']", "input[placeholder*='Search' i]",
                    "input[placeholder*='ค้นหา' i]", "input[role='combobox']",
                    "input[role='searchbox']", "input[type='text']:visible"):
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.fill(TEST_QUERY, timeout=4000)
                    print(f"[probe] filled via {sel!r}")
                    filled = True
                    break
            except Exception as e:
                print(f"  {sel!r} fill failed: {e}")
        if not filled:
            print("[probe] couldn't fill any input")
        else:
            time.sleep(3)
            try:
                page.keyboard.press("Enter")
                print("[probe] pressed Enter")
            except Exception as e:
                print(f"  Enter failed: {e}")
            try:
                page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:
                pass
            time.sleep(5)

        new = captured[before_count:]
        print(f"\n[probe] {len(new)} new XHR after fill+Enter")
        for r in new:
            print(f"\n  --- {r['method']} {r.get('_response', '?')}  {r['url'][:140]}")
            if r["post_data"]:
                print(f"    POST body: {r['post_data'][:400]}")
            if r["_body"]:
                print(f"    response[{len(r['_body'])}]: {r['_body'][:500]}")

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
