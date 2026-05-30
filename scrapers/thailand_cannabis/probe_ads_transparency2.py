"""Probe v2: try URL-based search params + broader input detection."""

import sys
from playwright.sync_api import sync_playwright

# Try several URL forms — Transparency Center may accept query string or path.
TEST_URLS = [
    "https://adstransparency.google.com/?region=TH&q=Nike",
    "https://adstransparency.google.com/search?q=Nike&region=TH",
    "https://adstransparency.google.com/advertiser/Nike?region=TH",
]


def dump_all_inputs(page) -> None:
    """Dump every input/contenteditable element on the page."""
    js = """
    () => {
        const out = [];
        document.querySelectorAll('input, textarea, [contenteditable="true"], [role="textbox"], [role="searchbox"], [role="combobox"]').forEach(el => {
            out.push({
                tag: el.tagName,
                type: el.type || null,
                role: el.getAttribute('role'),
                placeholder: el.placeholder || el.getAttribute('placeholder'),
                ariaLabel: el.getAttribute('aria-label'),
                id: el.id || null,
                className: typeof el.className === 'string' ? el.className.slice(0, 80) : null,
                visible: el.offsetParent !== null,
            });
        });
        return out;
    }
    """
    return page.evaluate(js)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = context.new_page()

        for url in TEST_URLS:
            print(f"\n[probe2] --- trying URL: {url}")
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception as e:
                print(f"  load issue: {e}")
            print(f"  final URL: {page.url}")
            print(f"  title:     {page.title()}")
            # Dump inputs
            inputs = dump_all_inputs(page)
            print(f"  inputs found: {len(inputs)}")
            for el in inputs[:8]:
                print(f"    {el}")
            # Look for results in body text
            try:
                txt = page.inner_text("body", timeout=4000)
            except Exception:
                txt = ""
            if "nike" in txt.lower():
                idx = txt.lower().find("nike")
                print(f"  'Nike' visible at idx={idx}: {txt[max(0,idx-30):idx+200]!r}")
            else:
                print(f"  'Nike' NOT visible in body (body len={len(txt)})")
                print(f"  body preview: {txt[:300]!r}")

        # Now try the interactive route on the bare page
        print(f"\n[probe2] --- interactive search attempt ---")
        page.goto("https://adstransparency.google.com/?region=TH", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1500)
        # Use Playwright's get_by_role for searchbox/textbox
        try:
            searchbox = page.get_by_role("combobox").first
            print(f"  found combobox, visible={searchbox.is_visible()}")
            searchbox.click(timeout=5000)
            searchbox.type("Nike", delay=50)
            page.wait_for_timeout(3000)
            page.screenshot(path="scrapers/thailand_cannabis/data/_probe_ads_searched.png", full_page=False)
            print("  saved screenshot after search: data/_probe_ads_searched.png")
            print(f"  URL after type: {page.url}")
            # Press Enter to commit
            searchbox.press("Enter")
            page.wait_for_timeout(3000)
            page.screenshot(path="scrapers/thailand_cannabis/data/_probe_ads_after_enter.png", full_page=False)
            print(f"  URL after Enter: {page.url}")
        except Exception as e:
            print(f"  combobox approach failed: {e}")

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
