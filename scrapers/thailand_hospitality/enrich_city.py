"""Reusable city contact-enrichment engine + method log.

Standardises the manual web-search harvest (the method that built the Udon Thani
dataset) so each new city is fast and consistent, and records WHICH query
templates and source domains actually yield contacts — the "proven ways" we
replay for the next city.

Per-city contacts  ->  data/contacts_<slug>.csv      (STANDARD schema below)
Method log         ->  data/_enrichment_log.csv      (every venue attempt)

The web search itself is run by the operator/agent; this module gives a uniform
schema, dedupe, merge, stats, and a proven-sources report so the harvest is
analysable and repeatable across cities.

CLI:
  python enrich_city.py stats <slug>
  python enrich_city.py proven           # which templates/sources yield contacts
  python enrich_city.py import-udon      # migrate the existing Udon file into the engine
  python enrich_city.py selftest
"""

import csv
import os
import sys
from datetime import datetime, timezone

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
LOG = os.path.join(DATA, "_enrichment_log.csv")

STANDARD = ["name", "venue_type", "phone", "email", "website", "facebook",
            "instagram", "line", "address", "city", "province", "note", "source"]

# Proven search templates, ranked by observed yield in Udon Thani. Reuse per city.
QUERY_TEMPLATES = [
    "{name} {city} phone address facebook",        # best all-round
    "{name} {city} restaurant phone address",      # restaurant segment
    "{name} {city} nightclub bar phone facebook",  # nightlife segment
    "{thai_name} {city} เบอร์โทร ที่อยู่",          # Thai-language fallback
]

# Source domains that reliably carried contact fields in search summaries.
# (Update from `proven` output as the log grows.)
PROVEN_SOURCES = [
    "facebook.com", "restaurantguru.com", "tripadvisor.com", "wanderlog.com",
    "ilovit.com", "udon-map.com", "resourceguide.udonmap.com", "trip.com",
    "evendo.com", "asiafirms.com", "th.polomap.com",
]

LOG_FIELDS = ["timestamp", "city", "venue", "outcome", "has_phone", "has_fb",
              "has_address", "n_fields", "query"]


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def contacts_path(slug: str) -> str:
    return os.path.join(DATA, f"contacts_{slug}.csv")


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def add(slug: str, records: list[dict], city: str = "", province: str = "") -> int:
    """Append records (dicts; STANDARD keys, name required) to the city file,
    deduping by normalised name. Also writes a method-log row per record."""
    path = contacts_path(slug)
    existing = {}
    if os.path.exists(path):
        for r in csv.DictReader(open(path, encoding="utf-8")):
            existing[_norm(r["name"])] = r
    added = 0
    for rec in records:
        name = (rec.get("name") or "").strip()
        if not name:
            continue
        row = {k: (rec.get(k) or "") for k in STANDARD}
        row["city"] = row["city"] or city
        row["province"] = row["province"] or province
        key = _norm(name)
        if key in existing:
            # fill blanks only
            for k in STANDARD:
                if not existing[key].get(k) and row.get(k):
                    existing[key][k] = row[k]
        else:
            existing[key] = row
            added += 1
        log(slug, row.get("city") or city, name, row, rec.get("query", ""))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=STANDARD)
        w.writeheader()
        for r in existing.values():
            w.writerow({k: r.get(k, "") for k in STANDARD})
    return added


def log(slug: str, city: str, venue: str, fields: dict, query: str = "") -> None:
    if slug.startswith("_"):     # don't pollute the shared log from selftests
        return
    has_phone = bool((fields.get("phone") or "").strip())
    has_fb = bool((fields.get("facebook") or "").strip())
    has_addr = bool((fields.get("address") or "").strip())
    n = sum(1 for k in ("phone", "email", "website", "facebook", "instagram",
                        "line", "address") if (fields.get(k) or "").strip())
    outcome = "hit" if has_phone else ("partial" if (has_fb or has_addr) else "miss")
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new:
            w.writeheader()
        w.writerow({"timestamp": _now(), "city": city, "venue": venue,
                    "outcome": outcome, "has_phone": int(has_phone),
                    "has_fb": int(has_fb), "has_address": int(has_addr),
                    "n_fields": n, "query": query})


def stats(slug: str) -> dict:
    path = contacts_path(slug)
    if not os.path.exists(path):
        return {"venues": 0}
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    g = lambda k: sum(1 for r in rows if (r.get(k) or "").strip())
    return {"venues": len(rows), "phone": g("phone"), "facebook": g("facebook"),
            "email": g("email"), "website": g("website"), "address": g("address")}


def proven_report() -> dict:
    """Aggregate the method log: hit rate + avg fields, overall and per city."""
    if not os.path.exists(LOG):
        return {}
    rows = list(csv.DictReader(open(LOG, encoding="utf-8")))
    if not rows:
        return {}
    def summarise(rs):
        n = len(rs)
        hits = sum(1 for r in rs if r["outcome"] == "hit")
        partial = sum(1 for r in rs if r["outcome"] == "partial")
        phones = sum(int(r["has_phone"]) for r in rs)
        return {"attempts": n, "hit_rate": round(hits / n, 2),
                "partial_rate": round(partial / n, 2),
                "phone_rate": round(phones / n, 2)}
    out = {"overall": summarise(rows), "by_city": {}}
    cities = {r["city"] for r in rows}
    for c in sorted(cities):
        out["by_city"][c] = summarise([r for r in rows if r["city"] == c])
    return out


def import_udon() -> int:
    """One-off: migrate the existing udon_barshow_contacts.csv into the engine
    as contacts_udonthani.csv (STANDARD schema), so Udon is part of the system."""
    src = os.path.join(DATA, "udon_barshow_contacts.csv")
    if not os.path.exists(src):
        sys.exit("udon_barshow_contacts.csv not found")
    # reuse the seeder's classifier for venue_type (repo root is 3 levels up)
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, repo)
    from krobjob.seed import classify
    recs = []
    for r in csv.DictReader(open(src, encoding="utf-8")):
        note = r.get("note", "")
        recs.append({
            "name": r["name"].split(" / ")[0],
            "venue_type": classify(note, r["name"]) or "bar",
            "phone": r.get("phone", ""), "email": r.get("email", ""),
            "website": r.get("website", ""), "facebook": r.get("facebook", ""),
            "address": r.get("address", ""), "note": note,
            "source": r.get("source", ""),
        })
    # write directly (skip per-row logging for the migration)
    path = contacts_path("udonthani")
    seen, rows = set(), []
    for rec in recs:
        k = _norm(rec["name"])
        if k in seen:
            continue
        seen.add(k)
        rec["city"], rec["province"] = "Udon Thani", "Udon Thani"
        rows.append({k2: rec.get(k2, "") for k2 in STANDARD})
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=STANDARD)
        w.writeheader()
        w.writerows(rows)
    print(f"[import-udon] wrote {len(rows)} venues -> {path}")
    return 0


def _selftest() -> int:
    slug = "_selftest_city"
    p = contacts_path(slug)
    if os.path.exists(p):
        os.remove(p)
    n1 = add(slug, [
        {"name": "Test Bar", "phone": "+66 42 111 222", "facebook": "fb/test",
         "venue_type": "bar", "query": "Test Bar X phone"},
        {"name": "Test Cafe", "facebook": "fb/cafe", "query": "Test Cafe X phone"},
    ], city="Testville", province="Test")
    n2 = add(slug, [{"name": "Test Bar", "address": "1 Road"}], city="Testville")  # merge
    s = stats(slug)
    ok = (n1 == 2 and n2 == 0 and s["venues"] == 2 and s["phone"] == 1
          and s["facebook"] == 2 and s["address"] == 1)
    print(f"  add new={n1} merge_added={n2} stats={s}")
    print("[selftest]", "PASS" if ok else "FAIL")
    os.remove(p)
    return 0 if ok else 1


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == "stats":
        print(stats(sys.argv[2]))
    elif cmd == "proven":
        import json
        print(json.dumps(proven_report(), indent=2))
    elif cmd == "import-udon":
        return import_udon()
    elif cmd == "selftest":
        return _selftest()
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
