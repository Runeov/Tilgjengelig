"""Authenticated weed.th contact-info fetcher.

Reads the session saved by weed_th_auth_login.py, then for each shop in a city's
CSV calls the gated tRPC endpoint that returns contact info one method at a time:

  GET https://weed.th/api/trpc/user.getDispensaryContactInfo
      ?input={"json":{"id":"<uuid>","contact_method":"<phone|email|line|...>"}}

Waits 5 seconds between *shops* (not per method, since the methods all hit the
same shop). The site's robots.txt only mandates 1s, but we pace slower to be
friendlier to the authenticated endpoint and reduce ban risk. Bails immediately
on 401 so you don't burn the whole CSV against a dead session.

USAGE
  # Sanity-test with 3 shops first
  python weed_th_auth_fetch_contacts.py "Udon Thani" --limit 3

  # Full run (resumable — re-run with --resume to skip already-fetched shops)
  python weed_th_auth_fetch_contacts.py "Udon Thani"
  python weed_th_auth_fetch_contacts.py "Udon Thani" --resume

  # Only fetch specific methods (default: all known methods)
  python weed_th_auth_fetch_contacts.py "Udon Thani" --methods phone,email,line

OUTPUT
  data/weed_th_contacts_<city>.csv  -- one row per shop, columns per method.
  Rewritten after every shop so a crash never loses prior work.

YOU ACCEPT (by running this)
  - Scraping login-gated content likely violates weed.th's terms of service
  - Your account may be banned and your IP may be blocked at any time
  - The script makes no attempt to evade detection — it just respects the
    site's stated crawl-delay and uses your real session
"""

import argparse
import csv
import json
import os
import random
import sys
import time
from typing import Optional

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.thailand_cannabis.common import DATA_DIR  # noqa: E402

AUTH_STATE = os.path.join(DATA_DIR, "weed_th_auth.json")
INPUT_CSV = os.path.join(DATA_DIR, "weed_th.csv")

TRPC_URL = "https://weed.th/api/trpc/user.getDispensaryContactInfo"
SHOPS_PREFIX = "https://weed.th/shop/"

# Contact methods we know exist (from public.getDispensary flags) + a couple of guesses.
DEFAULT_METHODS = [
    "phone", "email", "line", "website",
    "facebook", "instagram", "google_url", "whatsapp",
]

# robots.txt declares Crawl-delay: 1; we use 5s with +/-20% jitter so the
# request pattern isn't perfectly metronomic. Real sessions never tick at a
# fixed cadence; small jitter just makes the timing look like normal traffic
# rather than artificially regular.
SHOP_DELAY = 5.0
JITTER_FRAC = 0.2  # uniform [delay*0.8, delay*1.2]


def shop_sleep() -> None:
    lo = SHOP_DELAY * (1 - JITTER_FRAC)
    hi = SHOP_DELAY * (1 + JITTER_FRAC)
    time.sleep(random.uniform(lo, hi))


def load_session() -> requests.Session:
    """Load cookies from Playwright storage_state file into a requests.Session."""
    if not os.path.exists(AUTH_STATE):
        raise SystemExit(
            f"Auth state not found at {AUTH_STATE}.\n"
            "Run weed_th_auth_login.py first to log in and save your session."
        )
    with open(AUTH_STATE, "r", encoding="utf-8") as f:
        state = json.load(f)
    sess = requests.Session()
    sess.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://weed.th",
    })
    cookies = state.get("cookies", [])
    for c in cookies:
        # requests.cookies.set ignores Playwright's expires=-1 and domain prefixes correctly
        sess.cookies.set(
            name=c["name"],
            value=c["value"],
            domain=c["domain"].lstrip("."),
            path=c.get("path", "/"),
        )
    print(f"[fetch] loaded {len(cookies)} cookies from {AUTH_STATE}")
    return sess


def session_alive(sess: requests.Session, sample_uuid: str, sample_url: str) -> bool:
    """Make one test call to verify the session is logged in."""
    method = "phone"
    params = {"input": json.dumps({"json": {"id": sample_uuid, "contact_method": method}})}
    resp = sess.get(TRPC_URL, params=params, headers={"Referer": sample_url}, timeout=15)
    if resp.status_code == 401:
        return False
    if resp.status_code != 200:
        print(f"[fetch] WARN: test call returned {resp.status_code}: {resp.text[:200]}")
    return resp.status_code == 200


def fetch_one(sess: requests.Session, uuid: str, method: str, referer: str, timeout: int = 15) -> dict:
    """Call the contact API for a single (shop, method). Returns dict with status + value."""
    params = {"input": json.dumps({"json": {"id": uuid, "contact_method": method}})}
    try:
        resp = sess.get(TRPC_URL, params=params, headers={"Referer": referer}, timeout=timeout)
    except requests.RequestException as e:
        return {"status": "error", "error": str(e), "value": None}
    if resp.status_code == 401:
        return {"status": "unauthorized", "value": None}
    if resp.status_code == 404:
        return {"status": "not_found", "value": None}
    if resp.status_code != 200:
        return {"status": f"http_{resp.status_code}", "value": None, "error": resp.text[:200]}
    try:
        data = resp.json()
    except ValueError:
        return {"status": "non_json", "value": None, "error": resp.text[:200]}
    # tRPC response shape: {"result":{"data":{"json":{...}}}}  or {"error":{...}}
    if "error" in data:
        err = data["error"]
        msg = (err.get("json") or {}).get("message") or str(err)
        return {"status": "trpc_error", "value": None, "error": msg[:200]}
    try:
        payload = data["result"]["data"]["json"]
    except (KeyError, TypeError):
        return {"status": "shape_mismatch", "value": None, "error": str(data)[:200]}
    # The actual contact value is either a string directly or nested under 'value' / method name.
    if isinstance(payload, str):
        return {"status": "ok", "value": payload}
    if isinstance(payload, dict):
        for k in (method, "value", "contact", "url"):
            if k in payload and payload[k]:
                return {"status": "ok", "value": payload[k]}
        # Empty dict = no value but authenticated
        return {"status": "empty", "value": None, "error": str(payload)[:200]}
    return {"status": "unknown_payload", "value": None, "error": str(payload)[:200]}


def load_existing(out_path: str) -> dict[str, dict]:
    if not os.path.exists(out_path):
        return {}
    with open(out_path, "r", encoding="utf-8", newline="") as f:
        return {r["source_id"]: r for r in csv.DictReader(f) if r.get("source_id")}


def write_out(out_path: str, rows: list[dict], fieldnames: list[str]) -> None:
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("city", help="City to fetch (e.g. 'Udon Thani')")
    parser.add_argument("--limit", type=int, default=None, help="Only fetch first N shops (sanity-test mode)")
    parser.add_argument("--resume", action="store_true", help="Skip shops already in the output file")
    parser.add_argument("--methods", default=",".join(DEFAULT_METHODS),
                        help=f"Comma-separated contact methods to fetch (default: {','.join(DEFAULT_METHODS)}). "
                             f"Pass only what you need (e.g. 'phone,line') to cut per-shop request count.")
    parser.add_argument("--max-shops-per-run", type=int, default=None,
                        help="Stop after fetching N NEW shops in this invocation, then exit cleanly. "
                             "Combine with --resume across days to spread a large city over multiple runs.")
    args = parser.parse_args()

    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    if not methods:
        parser.error("--methods cannot be empty")

    sess = load_session()

    # Load city shops
    with open(INPUT_CSV, "r", encoding="utf-8", newline="") as f:
        all_rows = list(csv.DictReader(f))
    target_city = args.city.strip().lower()
    shops = [r for r in all_rows if (r.get("city") or "").strip().lower() == target_city]
    if not shops:
        print(f"No shops for city={args.city!r}. Available cities (top 10):")
        from collections import Counter
        for city, n in Counter(r.get("city", "") for r in all_rows).most_common(10):
            print(f"  {n:5d}  {city}")
        return 1

    safe = args.city.lower().replace(" ", "_")
    out_path = os.path.join(DATA_DIR, f"weed_th_contacts_{safe}.csv")
    fieldnames = ["source_id", "name", "city", "fetched_at"] + [f"weed_{m}" for m in methods] + ["errors"]

    existing = load_existing(out_path) if args.resume else {}
    if args.resume and existing:
        print(f"[fetch] resume: {len(existing)} shops already done in {out_path}")

    # Sanity-test the session against the first shop before iterating
    test = shops[0]
    print(f"[fetch] sanity test against {test['name']!r}...")
    if not session_alive(sess, test["source_id"], test["detail_url"]):
        print("\nERROR: session not authenticated (401).")
        print("Re-run weed_th_auth_login.py to refresh cookies.")
        return 2
    print("[fetch] session OK")

    if args.limit:
        shops = shops[: args.limit]

    remaining_shops = [s for s in shops if s["source_id"] not in existing]
    cap = args.max_shops_per_run
    this_run = remaining_shops[:cap] if cap else remaining_shops

    print(f"[fetch] city={args.city!r}  total_in_city={len(shops)}  "
          f"already_done={len(existing)}  this_run={len(this_run)}  "
          f"methods={methods}  delay={SHOP_DELAY}s+/-{int(JITTER_FRAC*100)}%")
    if cap and len(remaining_shops) > cap:
        print(f"[fetch] --max-shops-per-run {cap}: {len(remaining_shops) - cap} shops will be deferred "
              "(re-run with --resume to continue)")
    print(f"[fetch] output -> {out_path}")
    est = len(this_run) * (SHOP_DELAY + 0.1 * len(methods))
    print(f"[fetch] estimated runtime ~{est:.0f}s ({est/60:.1f} min)\n")

    # Output rows: start from existing (if resuming) so we never lose data
    out_rows: list[dict] = list(existing.values())
    written_sids = set(existing.keys())

    for i, shop in enumerate(this_run, 1):
        sid = shop["source_id"]
        if i > 1:
            shop_sleep()
        rec = {
            "source_id": sid,
            "name": shop["name"],
            "city": shop["city"],
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "errors": "",
        }
        method_summary = []
        errors = []
        bailed = False
        for m in methods:
            res = fetch_one(sess, sid, m, shop["detail_url"])
            if res["status"] == "unauthorized":
                print(f"\nERROR: HTTP 401 on shop #{i} method={m}. Session likely expired or banned.")
                print("Partial results already saved. Re-run weed_th_auth_login.py and then "
                      "this script with --resume to continue.")
                bailed = True
                break
            if res["status"] == "ok" and res["value"]:
                rec[f"weed_{m}"] = res["value"]
                method_summary.append(f"{m}={res['value']!r}")
            else:
                rec[f"weed_{m}"] = ""
                if res["status"] not in ("ok", "empty", "not_found"):
                    errors.append(f"{m}:{res['status']}")
        rec["errors"] = ";".join(errors)
        if bailed:
            # Persist what we got so far for this shop only if we got anything
            if any(rec.get(f"weed_{m}") for m in methods):
                out_rows.append(rec)
                written_sids.add(sid)
            write_out(out_path, out_rows, fieldnames)
            return 3

        out_rows.append(rec)
        written_sids.add(sid)
        # Persist after EVERY shop — cheap and crash-safe
        write_out(out_path, out_rows, fieldnames)

        summary = ", ".join(method_summary) if method_summary else "(no contacts found)"
        print(f"  [{i}/{len(this_run)}] {shop['name'][:35]:35s} | {summary[:120]}")

    print(f"\n[fetch] this run wrote {len(this_run)} new rows -> total {len(out_rows)} in {out_path}")
    found = {m: sum(1 for r in out_rows if r.get(f"weed_{m}")) for m in methods}
    print("[fetch] contacts found (cumulative):")
    for m, n in found.items():
        print(f"  weed_{m:12s} {n}/{len(out_rows)}")
    still_remaining = len(shops) - len(out_rows)
    if still_remaining > 0:
        print(f"\n[fetch] {still_remaining} shops still to do. Re-run with --resume "
              "(ideally on a later day if you used --max-shops-per-run).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
