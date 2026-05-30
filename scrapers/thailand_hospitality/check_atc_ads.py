"""Check Google Ads Transparency Center for each Wongnai shop.

Uses Google's internal RPC (no Playwright needed):
  POST https://adstransparency.google.com/anji/_/rpc/SearchService/SearchSuggestions

Returns identity-verified Google advertisers matching the query. Filters to
country=TH so we only count Thailand-verified advertisers.

Important caveat: ATC only lists advertisers Google has identity-verified.
Most small Thai SMBs won't appear regardless of whether they run ads. This
signal biases toward 'has Google verified them' (= larger / more sophisticated
business), not 'currently runs ads'.

Output adds per row:
  atc_match_count        number of TH-country verified-advertiser matches
  atc_has_match          '1' if count > 0
  atc_top_advertiser     name of the best match
  atc_top_advertiser_id  Google's AR... advertiser ID
  atc_advertiser_url     direct link to the advertiser's ATC page
  atc_check_status       ok | http_error | parse_error

Usage:
  python check_atc_ads.py udonthani --limit 5      # sanity
  python check_atc_ads.py udonthani --food-only    # restrict to food/drink
  python check_atc_ads.py udonthani --resume       # continue after a crash
"""

import argparse
import csv
import json
import os
import sys
import time

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
RPC_URL = "https://adstransparency.google.com/anji/_/rpc/SearchService/SearchSuggestions?authuser="

# Thailand region ID in ATC's region list (discovered via Playwright probe).
TH_REGION_ID = 2764
TH_COUNTRY_CODE = "TH"

# Per-shop pacing. Google internal RPCs typically tolerate ~10 req/s but we
# pace at 1.5s/req (~40 reqs/min) to stay well below any rate limit and
# leave room for retries.
REQUEST_DELAY = 1.5

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    "Origin": "https://adstransparency.google.com",
    "Referer": "https://adstransparency.google.com/?region=TH",
    "X-Same-Domain": "1",
    "X-Goog-AuthUser": "0",
}

NEW_FIELDS = [
    "atc_match_count", "atc_has_match",
    "atc_top_advertiser", "atc_top_advertiser_id", "atc_advertiser_url",
    "atc_check_status",
]


def call_search(query: str) -> dict:
    """Hit SearchSuggestions; return parsed response dict (or {} on error)."""
    payload = {"1": query, "2": 10, "3": 10, "4": [TH_REGION_ID], "5": {"1": 1}}
    data = {"f.req": json.dumps(payload, separators=(",", ":"))}
    try:
        r = requests.post(RPC_URL, headers=HEADERS, data=data, timeout=12)
    except requests.RequestException as e:
        return {"_error": f"req:{type(e).__name__}"}
    if r.status_code != 200:
        return {"_error": f"http:{r.status_code}"}
    try:
        return r.json()
    except Exception:
        return {"_error": "non_json"}


def filter_th_advertisers(response: dict) -> list[dict]:
    """Return only suggestions that have country='TH' AND look like advertisers
    (have an AR... ID). Domain-only entries (no advertiser ID) are skipped."""
    out: list[dict] = []
    for item in response.get("1", []) or []:
        if not isinstance(item, dict):
            continue
        country = item.get("3") or ""
        adv_id = item.get("2") or ""
        if country == TH_COUNTRY_CODE and adv_id.startswith("AR"):
            out.append(item)
    return out


def check_one(name: str) -> dict:
    """Look up `name` in ATC. Return per-shop fields."""
    out = {f: "" for f in NEW_FIELDS}
    resp = call_search(name)
    if "_error" in resp:
        out["atc_check_status"] = resp["_error"]
        return out
    th_matches = filter_th_advertisers(resp)
    out["atc_match_count"] = str(len(th_matches))
    out["atc_has_match"] = "1" if th_matches else "0"
    if th_matches:
        top = th_matches[0]
        out["atc_top_advertiser"] = top.get("1") or ""
        adv_id = top.get("2") or ""
        out["atc_top_advertiser_id"] = adv_id
        if adv_id:
            out["atc_advertiser_url"] = (
                f"https://adstransparency.google.com/advertiser/{adv_id}?region=TH"
            )
    out["atc_check_status"] = "ok"
    return out


def load_already_done(out_path: str) -> set:
    done: set = set()
    if not os.path.exists(out_path):
        return done
    with open(out_path, "r", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            sid = r.get("publicId") or r.get("id")
            if sid and r.get("atc_check_status") and r.get("atc_check_status") != "":
                done.add(sid)
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slug", help="Region slug matching input CSV (e.g. 'udonthani')")
    parser.add_argument("--limit", type=int, default=None, help="Only check N shops")
    parser.add_argument("--food-only", action="store_true", help="Skip non-food rows")
    parser.add_argument("--resume", action="store_true", help="Skip rows already checked")
    args = parser.parse_args()

    in_path = os.path.join(DATA_DIR, f"wongnai_{args.slug}.csv")
    out_path = os.path.join(DATA_DIR, f"atc_ads_{args.slug}.csv")
    if not os.path.exists(in_path):
        raise SystemExit(f"Input not found: {in_path}. Run scrape_wongnai.py {args.slug} first.")

    with open(in_path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"[atc] input: {len(rows):,} rows from {in_path}")
    if args.food_only:
        rows = [r for r in rows if r.get("is_likely_food") == "1"]
        print(f"[atc] --food-only: {len(rows):,} food rows")

    in_fields = list(rows[0].keys()) if rows else []
    out_fields = in_fields + [f for f in NEW_FIELDS if f not in in_fields]

    already = load_already_done(out_path) if args.resume else set()
    if already:
        print(f"[atc] resume: {len(already)} rows already checked")
    to_do = [r for r in rows if (r.get("publicId") or r.get("id")) not in already]
    if args.limit:
        to_do = to_do[: args.limit]
    est_min = len(to_do) * REQUEST_DELAY / 60
    print(f"[atc] to check: {len(to_do)} (est runtime ~{est_min:.0f} min @ {REQUEST_DELAY}s/req)")

    file_exists = os.path.exists(out_path)
    mode = "a" if (args.resume and file_exists) else "w"
    out_f = open(out_path, mode, encoding="utf-8", newline="")
    writer = csv.DictWriter(out_f, fieldnames=out_fields)
    if mode == "w":
        writer.writeheader()
        out_f.flush()

    hits = zeros = errors = 0
    try:
        for i, row in enumerate(to_do, 1):
            name = (row.get("displayName") or row.get("name_english")
                    or row.get("name_thai") or "").strip()
            if not name:
                row.update({f: "" for f in NEW_FIELDS})
                row["atc_check_status"] = "no_name"
                writer.writerow({k: row.get(k, "") for k in out_fields})
                out_f.flush()
                continue
            if i > 1:
                time.sleep(REQUEST_DELAY)
            fields = check_one(name)
            row.update(fields)
            writer.writerow({k: row.get(k, "") for k in out_fields})
            out_f.flush()
            status = fields["atc_check_status"]
            cnt = fields["atc_match_count"] or "0"
            if status == "ok" and int(cnt) > 0:
                hits += 1
                top = fields["atc_top_advertiser"][:35]
                print(f"  [{i:>4}/{len(to_do)}] HIT  {name[:30]:<30} -> {top} ({cnt} TH matches)")
            elif status == "ok":
                zeros += 1
                if i % 25 == 0 or i == len(to_do):
                    print(f"  [{i:>4}/{len(to_do)}] (no TH matches so far: zeros={zeros}, hits={hits})")
            else:
                errors += 1
                print(f"  [{i:>4}/{len(to_do)}] ERROR {name[:30]} -> {status}")
    finally:
        out_f.close()

    print(f"\n[atc] done: hits={hits}  zeros={zeros}  errors={errors}")
    print(f"[atc] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
