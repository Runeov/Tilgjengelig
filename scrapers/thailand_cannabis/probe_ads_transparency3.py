"""Probe v3: navigate to /search?q=... and wait for results to render.
Capture the actual API call that populates results so we can call it directly.
"""

import json
import sys
from playwright.sync_api import sync_playwright

QUERIES = ["Nike", "Wonderland Bangkok", "BoomTreeHC", "Cannabis First shop"]


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = context.new_page()

        for q in QUERIES:
            print(f"\n[probe3] === query: {q!r} ===")
            api_calls: list[dict] = []

            def on_response(resp, capture=api_calls):
                if resp.request.resource_type not in ("xhr", "fetch"):
                    return
                url = resp.url
                # Filter out images / static stuff
                if any(s in url.lower() for s in (".png", ".jpg", ".css", ".woff", ".svg", "/log?")):
                    return
                try:
                    body = resp.text()
                except Exception:
                    body = ""
                capture.append({
                    "status": resp.status,
                    "url": url,
                    "method": resp.request.method,
                    "body_len": len(body),
                    "body_preview": body[:400],
                })

            page.on("response", on_response)

            from urllib.parse import quote
            url = f"https://adstransparency.google.com/search?q={quote(q)}&region=TH"
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception as e:
                print(f"  load: {e}")

            # Wait longer for the search results component to populate
            page.wait_for_timeout(5000)

            # Look for result cards. Try a variety of selectors that match Material card patterns.
            print(f"  XHRs captured: {len(api_calls)}")
            for x in api_calls:
                # Likely API endpoints have meaningful paths
                if any(s in x["url"] for s in ("rpc", "Search", "/v", "advertiser")):
                    print(f"    {x['method']} {x['status']}  {x['url'][:160]}")
                    if x["body_len"] > 0:
                        print(f"      body_len={x['body_len']}  preview: {x['body_preview'][:200]}")

            # Look at the rendered DOM for result counts / card elements
            results_info = page.evaluate("""
                () => {
                    // Heuristic: count things that look like advertiser result cards
                    const all = Array.from(document.querySelectorAll('a[href*="/advertiser/"]'));
                    const links = all.map(a => ({href: a.href, text: (a.innerText || '').trim().slice(0, 100)}));
                    const noResults = document.body.innerText.includes('ไม่พบ') ||
                                      document.body.innerText.toLowerCase().includes('no results') ||
                                      document.body.innerText.toLowerCase().includes('no advertisers');
                    return {
                        advertiser_links: links.slice(0, 10),
                        link_count: links.length,
                        no_results_text: noResults,
                        body_text_preview: document.body.innerText.slice(0, 500),
                    };
                }
            """)
            print(f"  advertiser links found: {results_info['link_count']}")
            for link in results_info["advertiser_links"][:5]:
                print(f"    {link['text'][:60]:60s}  ->  {link['href']}")
            if results_info["no_results_text"]:
                print(f"  page indicates NO RESULTS")
            print(f"  body preview: {results_info['body_text_preview'][:300]!r}")

            page.remove_listener("response", on_response)

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
