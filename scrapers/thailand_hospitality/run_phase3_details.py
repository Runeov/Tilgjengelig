"""Phase 3 orchestrator: detail-page enrichment for each city's top-N shops.

For each city with a wongnai_<city>.csv, runs enrich_wongnai_details.py to
fetch per-shop Wongnai detail pages → adds telephone, address, hours, rating,
review_count, price_range, serves_cuisine, image_url.

Pacing: enrich_wongnai_details.py has its own 2.5s crawl delay. We add an
inter-city cool-off so successive cities don't pile up.

Usage:
  python run_phase3_details.py                    # default top-500/city, food-only, all cities found
  python run_phase3_details.py --top 1000         # bigger per-city cap
  python run_phase3_details.py --cities phuket,chiangmai
"""

import argparse
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")


def cities_with_wongnai_data() -> list[str]:
    """Discover cities by scanning data/ for wongnai_<city>.csv files."""
    out = []
    for fn in sorted(os.listdir(DATA_DIR)):
        if fn.startswith("wongnai_") and fn.endswith(".csv") \
                and "_detailed" not in fn and "_google" not in fn \
                and "_contacts_" not in fn:
            # Skip the country-wide file from the cannabis project
            slug = fn[len("wongnai_"):-len(".csv")]
            if slug in ("", "country"):
                continue
            out.append(slug)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cities", help="Comma-separated city slugs (default: all wongnai_*.csv files)")
    parser.add_argument("--top", type=int, default=500, help="Top-N per city (default 500)")
    parser.add_argument("--food-only", action="store_true", default=True)
    parser.add_argument("--inter-city-delay", type=int, default=60,
                        help="Seconds to sleep between cities (cool-off)")
    args = parser.parse_args()

    if args.cities:
        cities = [c.strip() for c in args.cities.split(",") if c.strip()]
    else:
        cities = cities_with_wongnai_data()
    print(f"[phase3] {len(cities)} cities to enrich: {', '.join(cities)}")
    print(f"[phase3] top {args.top} shops/city, food_only={args.food_only}, "
          f"inter-city delay {args.inter_city_delay}s")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    failures = []
    for i, city in enumerate(cities, 1):
        out_path = os.path.join(DATA_DIR, f"wongnai_{city}_detailed.csv")
        cmd = [sys.executable,
               os.path.join(SCRIPT_DIR, "enrich_wongnai_details.py"),
               city, "--limit", str(args.top), "--resume"]
        if args.food_only:
            cmd.append("--food-only")
        print(f"\n{'='*70}\n  [{i}/{len(cities)}] {city}\n{'='*70}")
        print(f"  cmd: {' '.join(cmd)}")
        t0 = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                              encoding="utf-8", errors="replace")
        elapsed = time.time() - t0
        ok = proc.returncode == 0
        for line in (proc.stdout or "").strip().splitlines()[-3:]:
            print(f"    {line}")
        print(f"  [{city}] {'DONE' if ok else 'FAILED'} in {elapsed:.0f}s ({elapsed/60:.1f} min)")
        if not ok:
            failures.append(city)
            for line in (proc.stderr or "").strip().splitlines()[-3:]:
                print(f"    ! {line}")
        if i < len(cities):
            print(f"    cool-off {args.inter_city_delay}s...")
            time.sleep(args.inter_city_delay)

    print(f"\nPhase 3 done. Failures: {len(failures)}: {failures}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
