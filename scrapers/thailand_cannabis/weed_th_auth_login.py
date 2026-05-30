"""Interactive helper: open weed.th in a real browser, let the user log in,
then save the resulting session (cookies + localStorage) to data/weed_th_auth.json
so the contact-fetch script can reuse it without driving the browser per shop.

USAGE
  python weed_th_auth_login.py

WHAT IT DOES
  1. Opens a visible Chromium window pointed at https://weed.th/login
  2. Waits for you to:
       (a) sign in (or sign up + verify your email) — do this manually
       (b) confirm in this terminal by pressing Enter
  3. Saves the authenticated session state to data/weed_th_auth.json
  4. weed_th_auth_fetch_contacts.py then reads that file to call the
     gated API endpoints via plain HTTP requests (no browser per shop).

RE-RUN WHEN
  - First time setting up
  - After cookies expire (typically days to weeks)
  - If the fetch script reports HTTP 401 mid-run

YOU ACCEPT (by running this)
  - You created a weed.th account yourself
  - You understand that scraping login-gated content with that account
    may violate weed.th's terms of service
  - You accept the risk of account ban / IP block
  - This tool does NOT create accounts, solve captchas, or bypass any
    security check — you do the login yourself in a real browser
"""

import os
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.thailand_cannabis.common import DATA_DIR  # noqa: E402

LOGIN_URL = "https://weed.th/login"
STATE_PATH = os.path.join(DATA_DIR, "weed_th_auth.json")


def main() -> int:
    print("=" * 70)
    print(" weed.th auth login helper")
    print("=" * 70)
    print()
    print("A Chromium window is about to open. In that window:")
    print("  1. Sign in to weed.th (or sign up + verify your email)")
    print("  2. Once logged in, return to THIS terminal and press Enter")
    print("  3. Do NOT close the browser window — this script will close it")
    print()
    print(f"Auth state will be saved to:  {STATE_PATH}")
    print()
    input("Press Enter to launch the browser... ")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"WARN: initial navigation failed ({e}); browser is still open, proceed manually.")

        print()
        print("Browser is open. Log in to weed.th, then return here.")
        print("When you see your account is logged in (top-right menu, etc.),")
        input("press Enter HERE to save the session and quit... ")

        # Quick sanity check: do we have any non-trivial cookies on the weed.th domain?
        cookies = context.cookies("https://weed.th")
        meaningful = [c for c in cookies if c.get("value") and len(c["value"]) > 8]
        print(f"\n[auth] {len(cookies)} cookies on weed.th, {len(meaningful)} look meaningful")
        if not meaningful:
            print("[auth] WARNING: no substantial cookies captured. Did you actually log in?")
            ans = input("Save anyway? [y/N] ").strip().lower()
            if ans != "y":
                print("[auth] Aborted, nothing written.")
                browser.close()
                return 1

        context.storage_state(path=STATE_PATH)
        print(f"[auth] saved session state -> {STATE_PATH}")
        browser.close()

    print()
    print("Next step:")
    print("  python scrapers/thailand_cannabis/weed_th_auth_fetch_contacts.py "
          '"Udon Thani" --limit 3')
    print("(start with --limit 3 to verify the session works before burning rate)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
