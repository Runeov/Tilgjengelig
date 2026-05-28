"""Merge thaidispos (licensed tier) with weed.th (bulk-listed tier).

For each thaidispos entry, we fuzzy-match against weed.th by normalized name.
Matches with similarity above MATCH_THRESHOLD AND matching city are flagged as
licensed=True in the merged universe. Unmatched thaidispos entries are still
included (so the merged file is a superset of both sources).

Outputs:
  data/merged.csv     — union of both sources with licensed flag
  data/matches.csv    — the cross-reference matches with similarity scores
  data/summary.json   — counts for downstream report.py
"""

import csv
import json
import os
import sys
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.thailand_cannabis.common import (  # noqa: E402
    DATA_DIR,
    DISPENSARY_FIELDS,
    normalize_city,
    normalize_name,
    write_csv,
)

THAIDISPOS_CSV = os.path.join(DATA_DIR, "thaidispos.csv")
WEEDTH_CSV = os.path.join(DATA_DIR, "weed_th.csv")
MERGED_CSV = os.path.join(DATA_DIR, "merged.csv")
MATCHES_CSV = os.path.join(DATA_DIR, "matches.csv")
SUMMARY_JSON = os.path.join(DATA_DIR, "summary.json")

# Word-set Jaccard threshold for declaring a match. Character-level similarity
# (SequenceMatcher.ratio) is too lenient — "stash rooftop" vs "high rooftop"
# scores 0.72 just from a shared substring. Jaccard on whole tokens avoids that.
JACCARD_THRESHOLD = 0.4


def load_csv(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def char_ratio(a: str, b: str) -> float:
    """Character-level similarity, kept only for diagnostic output."""
    return SequenceMatcher(None, a, b).ratio()


def jaccard(a: str, b: str) -> float:
    """Word-set Jaccard similarity. Both args must be already-normalized strings."""
    ta = set(a.split())
    tb = set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def city_match(a: str, b: str) -> bool:
    """Match cities including the Koh Samui/Surat Thani island-province case."""
    na, nb = normalize_city(a), normalize_city(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # Koh Samui is an island in Surat Thani province; weed.th uses the province.
    if {na, nb} == {"koh samui", "surat thani"}:
        return True
    # Substring (e.g. "chiang mai" matches "old city chiang mai")
    return na in nb or nb in na


def find_match(licensed: dict, listed: list[dict]) -> tuple[dict | None, float, float]:
    """Find best weed.th match for a licensed (thaidispos) record.

    Returns (match_row_or_none, best_jaccard, char_ratio_at_best_jaccard).
    """
    target_name = normalize_name(licensed["name"])
    if not target_name:
        return None, 0.0, 0.0

    best: dict | None = None
    best_j = 0.0
    best_r = 0.0
    for row in listed:
        if not city_match(licensed.get("city", ""), row.get("city", "")):
            continue
        listed_norm = normalize_name(row["name"])
        j = jaccard(target_name, listed_norm)
        if j > best_j:
            best_j = j
            best_r = char_ratio(target_name, listed_norm)
            best = row
    if best_j < JACCARD_THRESHOLD:
        return None, best_j, best_r
    return best, best_j, best_r


def merge() -> dict:
    licensed_rows = load_csv(THAIDISPOS_CSV)
    listed_rows = load_csv(WEEDTH_CSV)

    print(f"[merge] licensed (thaidispos): {len(licensed_rows)}")
    print(f"[merge] listed   (weed.th):   {len(listed_rows):,}")

    # Cross-reference
    matches: list[dict] = []
    matched_weedth_uuids: set[str] = set()
    unmatched_licensed: list[dict] = []

    for lic in licensed_rows:
        match, jacc, ratio = find_match(lic, listed_rows)
        if match:
            matches.append({
                "licensed_name": lic["name"],
                "licensed_city": lic["city"],
                "listed_name": match["name"],
                "listed_city": match["city"],
                "listed_uuid": match["source_id"],
                "listed_url": match["detail_url"],
                "jaccard": round(jacc, 3),
                "char_ratio": round(ratio, 3),
            })
            matched_weedth_uuids.add(match["source_id"])
            print(f"  [MATCH jaccard={jacc:.2f} ratio={ratio:.2f}] {lic['name']!r} <-> {match['name']!r}")
        else:
            unmatched_licensed.append(lic)
            print(f"  [no match best_jaccard={jacc:.2f}] {lic['name']!r} ({lic['city']})")

    # Build merged universe: all weed.th rows + any thaidispos rows that didn't match.
    # Flag licensed=True for: matched weed.th rows + all thaidispos rows.
    merged: list[dict] = []
    for row in listed_rows:
        out = dict(row)
        out["licensed"] = "True" if row["source_id"] in matched_weedth_uuids else "False"
        merged.append(out)
    for row in unmatched_licensed:
        out = dict(row)
        out["licensed"] = "True"
        merged.append(out)

    write_csv(MERGED_CSV, merged, DISPENSARY_FIELDS)
    write_csv(MATCHES_CSV, matches, [
        "licensed_name", "licensed_city", "listed_name", "listed_city",
        "listed_uuid", "listed_url", "jaccard", "char_ratio",
    ])

    summary = {
        "licensed_count": len(licensed_rows),
        "listed_count": len(listed_rows),
        "matched_count": len(matches),
        "unmatched_licensed_count": len(unmatched_licensed),
        "merged_count": len(merged),
        "jaccard_threshold": JACCARD_THRESHOLD,
        "licensed_ratio_of_listed": (
            round(len(matches) / len(listed_rows), 6) if listed_rows else None
        ),
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\n[merge] matched: {len(matches)}/{len(licensed_rows)} licensed dispensaries found in weed.th")
    print(f"[merge] merged universe: {len(merged):,} shops")
    print(f"[merge] wrote {MERGED_CSV}")
    print(f"[merge] wrote {MATCHES_CSV}")
    print(f"[merge] wrote {SUMMARY_JSON}")
    return summary


if __name__ == "__main__":
    merge()
