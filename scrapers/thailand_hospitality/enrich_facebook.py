"""Pull phone numbers from the Facebook pages we already have on file.

Many enriched Udon venues have a Facebook URL but no phone (the search summaries
didn't surface one). This tool visits each such page and extracts a phone number
from tel: links, the page's structured data, and visible "about"/contact text.

⚠️ NEEDS NETWORK EGRESS to facebook.com / mbasic.facebook.com. The default Claude
Code web session blocks it (403) — run this from a network-enabled session. It is
best-effort: Facebook gates a lot behind login, so expect partial yield. It never
overwrites an existing phone; results go to a review file you merge deliberately.

Usage:
  python enrich_facebook.py --check                 # network preflight
  python enrich_facebook.py                         # enrich rows missing a phone
  python enrich_facebook.py --limit 20 --delay 8    # throttle
  python enrich_facebook.py --selftest              # offline: verify the extractor
  python enrich_facebook.py --merge                 # fold reviewed phones into contacts CSV

Output: data/_fb_phone_enrichment.csv  (name, facebook, found_phone, source_field)
"""

import argparse
import csv
import os
import re
import sys
import time

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CONTACTS = os.path.join(DATA, "udon_barshow_contacts.csv")
OUT = os.path.join(DATA, "_fb_phone_enrichment.csv")
UA = ("Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Mobile Safari/537.36")

# Thai phone shapes: +66 / 0 followed by 8-9 digits, with optional spaces/dashes.
_PHONE_RE = re.compile(r"""(?x)
    (?:\+?66[\s\-]?|0)                 # country code or leading 0
    \d{1,2}[\s\-]?\d{3}[\s\-]?\d{3,4}  # the rest
""")
_TEL_RE = re.compile(r'tel:([+\d\s\-]{8,})', re.I)


def normalize_phone(s: str) -> str | None:
    digits = re.sub(r"[^\d+]", "", s)
    if digits.startswith("0") and len(digits) in (9, 10):
        digits = "+66" + digits[1:]
    elif digits.startswith("66"):
        digits = "+" + digits
    if not digits.startswith("+66"):
        return None
    # +66 plus 8 or 9 national digits
    if not (11 <= len(digits) <= 12):
        return None
    body = digits[3:]            # 8 (landline) or 9 (mobile) national digits
    if len(body) not in (8, 9):
        return None
    return f"+66 {body[:2]} {body[2:5]} {body[5:]}"


def extract_phones(html: str) -> list[tuple[str, str]]:
    """Return [(normalized_phone, source_field)] found in the page."""
    out, seen = [], set()

    def add(raw, field):
        n = normalize_phone(raw)
        if n and n not in seen:
            seen.add(n)
            out.append((n, field))

    for m in _TEL_RE.findall(html):
        add(m, "tel-link")
    # og:description / meta description often carry the contact line
    for m in re.findall(r'<meta[^>]+content="([^"]+)"', html):
        if any(c.isdigit() for c in m):
            for p in _PHONE_RE.findall(m):
                add(p, "meta")
    # visible text fallback
    for p in _PHONE_RE.findall(re.sub(r"<[^>]+>", " ", html)):
        add(p, "text")
    return out


def fetch(url: str, delay: float) -> str | None:
    import requests
    time.sleep(delay)
    # mbasic exposes more without JS/login than www.
    for u in (url.replace("www.facebook.com", "mbasic.facebook.com"), url):
        try:
            r = requests.get(u, headers={"User-Agent": UA, "Accept-Language": "en"},
                             timeout=30)
            if r.status_code == 200 and r.text:
                return r.text
        except Exception:
            continue
    return None


def _rows_missing_phone():
    for r in csv.DictReader(open(CONTACTS, encoding="utf-8")):
        if (r.get("facebook") or "").strip() and not (r.get("phone") or "").strip():
            yield r


def cmd_check() -> int:
    import requests
    try:
        r = requests.get("https://mbasic.facebook.com/", headers={"User-Agent": UA}, timeout=15)
        ok = r.status_code == 200
        print(f"  mbasic.facebook.com -> HTTP {r.status_code} {'OK' if ok else 'BLOCKED'}")
        return 0 if ok else 2
    except Exception as e:
        print(f"  facebook unreachable: {type(e).__name__}: {str(e)[:80]}")
        return 2


def run(limit, delay) -> int:
    targets = list(_rows_missing_phone())
    if limit:
        targets = targets[:limit]
    print(f"[fb] {len(targets)} venues have a Facebook page but no phone")
    found = []
    for i, r in enumerate(targets, 1):
        html = fetch(r["facebook"], delay)
        phones = extract_phones(html) if html else []
        if phones:
            phone, field = phones[0]
            found.append((r["name"], r["facebook"], phone, field))
            print(f"  [{i}/{len(targets)}] {r['name'][:30]:32} {phone}  ({field})")
        else:
            print(f"  [{i}/{len(targets)}] {r['name'][:30]:32} —")
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "facebook", "found_phone", "source_field"])
        w.writerows(found)
    print(f"[fb] {len(found)} phones found -> {OUT} (review, then --merge)")
    return 0


def cmd_merge() -> int:
    if not os.path.exists(OUT):
        sys.exit(f"no {OUT}; run the enrichment first")
    found = {r["name"]: r["found_phone"] for r in csv.DictReader(open(OUT, encoding="utf-8"))}
    rows = list(csv.DictReader(open(CONTACTS, encoding="utf-8")))
    fields = rows[0].keys()
    n = 0
    for r in rows:
        if not (r.get("phone") or "").strip() and r["name"] in found:
            r["phone"] = found[r["name"]]
            r["source"] = (r.get("source") or "") + " + fb-phone"
            n += 1
    with open(CONTACTS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fields))
        w.writeheader()
        w.writerows(rows)
    print(f"[fb] merged {n} phones into {CONTACTS}")
    return 0


def selftest() -> int:
    sample = '''<html><head>
      <meta property="og:description" content="Cold beer & pool. Call 081-234-5678 daily.">
      </head><body><a href="tel:+66942223333">Call us</a>
      <div>Line/Tel 042 247 450</div></body></html>'''
    got = extract_phones(sample)
    phones = {p for p, _ in got}
    expect = {"+66 81 234 5678", "+66 94 222 3333", "+66 42 247 450"}
    ok = expect.issubset(phones)
    for p, field in got:
        print(f"  found {p}  ({field})")
    # normalization unit checks
    cases = {"0812345678": "+66 81 234 5678", "+66942223333": "+66 94 222 3333",
             "042-247-450": "+66 42 247 450", "12345": None}
    for raw, want in cases.items():
        got1 = normalize_phone(raw)
        flag = "ok " if got1 == want else "BAD"
        if got1 != want:
            ok = False
        print(f"  [{flag}] normalize({raw!r}) = {got1!r} (want {want!r})")
    print("[selftest]", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--check", action="store_true")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--merge", action="store_true")
    p.add_argument("--limit", type=int)
    p.add_argument("--delay", type=float, default=6.0)
    a = p.parse_args()
    if a.selftest:
        return selftest()
    if a.check:
        return cmd_check()
    if a.merge:
        return cmd_merge()
    if cmd_check() != 0:
        print("[abort] Facebook unreachable — run from a network-enabled session.")
        return 2
    return run(a.limit, a.delay)


if __name__ == "__main__":
    sys.exit(main())
