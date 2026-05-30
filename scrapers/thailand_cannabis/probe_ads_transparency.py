"""Probe: can we query Google Ads Transparency Center programmatically for
Thai cannabis shop names to identify active Google Ads advertisers?

Opens adstransparency.google.com in headless Chromium, searches for a few
test queries, and reports:
  - Page structure (search input, results layout)
  - What XHR/fetch calls the search triggers
  - Whether results include advertiser ID, ad count, ad types, regions
  - Whether the page is scrapable without auth/captcha
"""

import re
import sys
import time

from playwright.sync_api import sync_playwright

# Mix of known international brand + a couple of Udon Thani shop names from our data
QUERIES = [
    "Nike",                          # control — should have lots of results
    "Wonderland Bangkok",            # licensed dispensary, known brand
    "BoomTreeHC",                    # Udon Thani shop, smaller
    "Cannabis First shop",           # Udon Thani shop with phone in our data
]

BASE_URL = "https://adstransparency.google.com/?region=TH"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = context.new_page()

        xhrs: list[dict] = []

        def on_response(resp):
            rt = resp.request.resource_type
            if rt not in ("xhr", "fetch"):
                return
            url = resp.url
            # Only log if URL has something interesting
            if not any(s in url.lower() for s in ("search", "advertiser", "creative", "transparency", "rpc")):
                return
            try:
                body = resp.text()
            except Exception:
                body = "<unreadable>"
            xhrs.append({
                "status": resp.status,
                "url": url,
                "body_preview": body[:500],
            })

        page.on("response", on_response)

        print(f"[probe] navigating to {BASE_URL}")
        try:
            page.goto(BASE_URL, wait_until="networkidle", timeout=45000)
        except Exception as e:
            print(f"[probe] initial load issue: {e}")

        # Take a screenshot for visual reference
        try:
            page.screenshot(path="scrapers/thailand_cannabis/data/_probe_ads_initial.png", full_page=False)
            print("[probe] saved screenshot: data/_probe_ads_initial.png")
        except Exception as e:
            print(f"[probe] screenshot failed: {e}")

        # Dump basic page structure
        print(f"[probe] page title: {page.title()}")
        print(f"[probe] URL after load: {page.url}")

        # Look for search input
        possible_inputs = page.locator("input[type='search'], input[role='combobox'], input[placeholder*='search' i], input[aria-label*='search' i]")
        n = possible_inputs.count()
        print(f"[probe] possible search inputs found: {n}")
        for i in range(min(n, 3)):
            el = possible_inputs.nth(i)
            try:
                outer = el.evaluate("e => ({tag: e.tagName, id: e.id, placeholder: e.placeholder, ariaLabel: e.getAttribute('aria-label')})")
                print(f"  input[{i}]: {outer}")
            except Exception:
                pass

        # Try each query
        for q in QUERIES:
            print(f"\n[probe] --- query: {q!r} ---")
            xhrs.clear()
            try:
                # Find any visible text input
                search = page.locator("input[type='search'], input[role='combobox']").first
                search.click(timeout=8000)
                # Clear via keyboard
                search.press("Control+A")
                search.press("Delete")
                search.type(q, delay=40)
                page.wait_for_timeout(2500)  # let suggestions/results populate
            except Exception as e:
                print(f"  ! could not interact with search input: {e}")
                continue

            # Capture whatever shows after typing
            try:
                body_text = page.inner_text("body", timeout=4000)
            except Exception:
                body_text = ""
            # Look for advertiser-name-like results
            # Print snippet around the query
            idx = body_text.lower().find(q.lower())
            if idx >= 0:
                print(f"  visible context near match: {body_text[max(0,idx-50):idx+200]!r}")
            else:
                print("  query text not visible in page body after typing")

            # Print any XHRs captured during this query
            print(f"  XHRs during query: {len(xhrs)}")
            for x in xhrs[:5]:
                print(f"    {x['status']}  {x['url'][:120]}")
                if x['body_preview'].strip():
                    print(f"      body: {x['body_preview'][:200]}")

        # Final screenshot
        try:
            page.screenshot(path="scrapers/thailand_cannabis/data/_probe_ads_after.png", full_page=True)
            print("\n[probe] saved final screenshot: data/_probe_ads_after.png")
        except Exception:
            pass

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
