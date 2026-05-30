"""Probe: how does weed.th reveal a shop's phone when the Call button is clicked?

Opens BoomTreeHC shop URL in headless Chromium, intercepts ALL network requests
made by the page, clicks the Call button, then reports:
  - What URLs were requested before and after the click
  - Any tel: links / phone-like text that appeared in the DOM after click
  - The response body of any new API request made on click

The answer informs the scraper strategy:
  - If a single weed.th API endpoint is hit (e.g., /api/shops/{uuid}/contact),
    we can call it directly without a browser at scale.
  - If the reveal is purely a DOM mutation from pre-loaded data, we look for
    that data in the bundle.
  - If neither, we drive a real browser for every shop.
"""

import re
import sys
import time

from playwright.sync_api import sync_playwright

TARGET_URL = "https://weed.th/shop/ae7ba0c9-5842-4387-8245-7c6172141f8c/udon-thani/boomtreehc"

# Patterns that indicate a phone number is present
PHONE_PATTERNS = [
    re.compile(r"\+66\s?[\d \-]{6,15}"),
    re.compile(r"\b0[689]\d[\d \-]{6,12}"),
    re.compile(r'href=["\']tel:[^"\']+'),
]


def find_phones(text: str) -> list[str]:
    hits: list[str] = []
    for pat in PHONE_PATTERNS:
        hits.extend(m.group(0) for m in pat.finditer(text))
    return hits


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        all_requests: list[dict] = []
        responses_after_click: list[dict] = []
        click_t0 = {"v": None}  # mutable container so handlers can mutate

        def on_request(req):
            t = time.time()
            all_requests.append({"t": t, "method": req.method, "url": req.url})

        def on_response(resp):
            t = time.time()
            if click_t0["v"] is None or t < click_t0["v"]:
                return  # ignore pre-click responses
            # Only interesting if it's an XHR/fetch (skip images, fonts, CSS, JS chunks)
            rt = resp.request.resource_type
            if rt not in ("xhr", "fetch"):
                return
            try:
                body = resp.text()
            except Exception:
                body = "<could not read body>"
            responses_after_click.append({
                "url": resp.url,
                "status": resp.status,
                "resource_type": rt,
                "body": body[:2000],
            })

        page.on("request", on_request)
        page.on("response", on_response)

        print(f"[probe] navigating to {TARGET_URL}")
        page.goto(TARGET_URL, wait_until="networkidle", timeout=45000)

        # Baseline: scan HTML for phones BEFORE click
        html_before = page.content()
        phones_before = find_phones(html_before)
        print(f"[probe] phones in DOM BEFORE click: {phones_before or '(none)'}")
        print(f"[probe] requests so far: {len(all_requests)}")

        # Find the Call button. From the static HTML probe we know it's a <div>
        # containing the text "Call". Use Playwright's text locator.
        print(f"[probe] looking for Call button...")
        candidates = page.locator("text=Call")
        n = candidates.count()
        print(f"[probe] found {n} elements containing 'Call'")
        if n == 0:
            print("ERROR: no Call element found.")
            browser.close()
            return 1
        # Print each candidate's outer HTML (truncated) so we know which to click
        for i in range(min(n, 5)):
            el = candidates.nth(i)
            try:
                outer = el.evaluate("e => e.outerHTML")
                print(f"  candidate[{i}]: {outer[:150]}")
            except Exception as e:
                print(f"  candidate[{i}]: <error: {e}>")

        # Click the first one. It's a <div>, may need to climb to a clickable parent.
        target = candidates.first
        click_t0["v"] = time.time()
        print(f"[probe] clicking Call button at t0={click_t0['v']:.3f}")
        try:
            target.click(timeout=8000)
        except Exception as e:
            print(f"[probe] direct click failed ({e}); trying parent")
            try:
                target.locator("xpath=..").click(timeout=8000)
            except Exception as e2:
                print(f"[probe] parent click also failed: {e2}")

        # Give the page a moment to respond
        page.wait_for_timeout(2500)

        html_after = page.content()
        phones_after = find_phones(html_after)
        new_phones = [p for p in phones_after if p not in phones_before]
        print(f"\n[probe] phones in DOM AFTER click: {phones_after or '(none)'}")
        print(f"[probe] NEW phones (delta): {new_phones or '(none)'}")

        print(f"\n[probe] {len(responses_after_click)} XHR/fetch responses after click:")
        for r in responses_after_click:
            print(f"  --- {r['status']} {r['resource_type']} {r['url']}")
            body_preview = r["body"][:600].replace("\n", " ")
            print(f"      body: {body_preview}")

        # Also check for popup windows, modals, alerts that may have opened
        # by querying any newly visible elements containing phone-like text
        print(f"\n[probe] full DOM text search for any phone-pattern hit...")
        all_text = page.inner_text("body", timeout=5000)
        text_phones = find_phones(all_text)
        print(f"[probe] phones in visible text: {text_phones or '(none)'}")

        # If no phone yet, page may have opened a tel: link / new window.
        # Check for any modal/dialog elements that appeared.
        modals = page.locator('[role="dialog"], .modal, [class*="modal"], [class*="popup"]')
        print(f"[probe] modal/dialog elements present: {modals.count()}")
        for i in range(min(modals.count(), 3)):
            try:
                txt = modals.nth(i).inner_text()
                print(f"  modal[{i}] text: {txt[:200]}")
            except Exception:
                pass

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
