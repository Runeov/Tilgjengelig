"""Split data/leads_country.csv into per-canonical-city files.

After lead_qualify.py --country runs, this writes data/leads_<canonical>.csv
for every province present in the country file. The per-city reports
(report_city.py) automatically pick those up.

Usage:
  python split_leads_country.py
"""

import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.thailand_cannabis.common import DATA_DIR  # noqa: E402
from scrapers.thailand_cannabis.city_normalize import canonical_city  # noqa: E402

INPUT = os.path.join(DATA_DIR, "leads_country.csv")


def main() -> int:
    if not os.path.exists(INPUT):
        print(f"ERROR: {INPUT} not found. Run lead_qualify.py --country first.", file=sys.stderr)
        return 1
    with open(INPUT, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        by_city: dict[str, list[dict]] = defaultdict(list)
        for r in reader:
            city = canonical_city(r.get("city", ""))
            by_city[city].append(r)

    written = 0
    for city, rows in sorted(by_city.items(), key=lambda kv: -len(kv[1])):
        safe = city.lower().replace(" ", "_").replace("(", "").replace(")", "")
        out_path = os.path.join(DATA_DIR, f"leads_{safe}.csv")
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        written += 1
        if written <= 10:
            print(f"  wrote {out_path:60s} ({len(rows):>4} rows)")
    print(f"\nTotal: {written} per-city files written to {DATA_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
