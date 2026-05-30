"""Multi-city orchestrator for Thailand hospitality discovery.

Runs `scrape_wongnai` (bulk) + `scrape_osm` (lodging/attractions) for each
city in the target list, then optionally `merge_hospitality` per city.

Per-city work is skipped if the output CSV already exists (resume-safe).
Each city runs sequentially with a courtesy gap between scrapes to avoid
re-triggering Wongnai's IP-level rate limit (~80 reqs / 2 min).

Usage:
  python run_all_cities.py                          # default tourism+regional list
  python run_all_cities.py --cities bangkok,phuket  # custom list
  python run_all_cities.py --max-pages 100          # cap Wongnai pages per city (default 100 = 2K shops)
  python run_all_cities.py --skip-osm               # skip OSM step
  python run_all_cities.py --skip-merge             # don't auto-merge per city
  python run_all_cities.py --list                   # show target list, exit
"""

import argparse
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

# Default targets: tourism cities + major regional centers + Udon Thani.
# Slugs were verified via /_api/regions.json. Ayutthaya is intentionally excluded
# (slug returns Chonburi shops — needs investigation).
DEFAULT_CITIES = [
    "bangkok",      # 809K total, capped to top N
    "phuket",       # 40K
    "chiangmai",    # 40K
    "1009-pattaya", # 14K (special slug)
    "krabi",        # 13K
    "surat-thani",  # 15K (includes Koh Samui area)
    "huahin",       # 12K
    "chiangrai",    # 8.5K
    "khonkaen",     # 33K
    "korat",        # 45K (Nakhon Ratchasima)
    "udonthani",    # 2.2K (already done)
]


def run(cmd: list[str], label: str) -> bool:
    """Run a subprocess, log stdout. Returns True on success."""
    print(f"\n>>> {label}\n    cmd: {' '.join(cmd)}")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                          encoding="utf-8", errors="replace")
    elapsed = time.time() - t0
    if proc.returncode == 0:
        # Print last 3 lines of stdout (summary)
        for line in (proc.stdout or "").strip().splitlines()[-3:]:
            print(f"    {line}")
        print(f"    [{label}] DONE in {elapsed:.0f}s")
        return True
    else:
        print(f"    [{label}] FAILED rc={proc.returncode} ({elapsed:.0f}s)")
        for line in (proc.stderr or "").strip().splitlines()[-5:]:
            print(f"    ! {line}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cities", help="Comma-separated city slugs (default: built-in tourism list)")
    parser.add_argument("--max-pages", type=int, default=100,
                        help="Max Wongnai pages per city (default 100 = ~2K shops)")
    parser.add_argument("--skip-wongnai", action="store_true")
    parser.add_argument("--skip-osm", action="store_true")
    parser.add_argument("--skip-merge", action="store_true")
    parser.add_argument("--inter-city-delay", type=int, default=30,
                        help="Seconds to sleep between cities (cool-off for rate limits)")
    parser.add_argument("--wongnai-delay", type=float, default=2.5,
                        help="Wongnai page-fetch delay in seconds. Use 15+ for retry "
                             "runs after a 403/IP ban.")
    parser.add_argument("--list", action="store_true", help="Print target list and exit")
    args = parser.parse_args()

    cities = (args.cities or "").split(",") if args.cities else DEFAULT_CITIES
    cities = [c.strip() for c in cities if c.strip()]

    if args.list:
        for c in cities:
            print(f"  {c}")
        return 0

    print(f"[orchestrator] {len(cities)} cities: {', '.join(cities)}")
    print(f"[orchestrator] max wongnai pages per city: {args.max_pages}  "
          f"(~{args.max_pages * 20} shops/city)")
    print(f"[orchestrator] inter-city cool-off: {args.inter_city_delay}s")

    failures = []
    for i, city in enumerate(cities, 1):
        print(f"\n{'='*70}\n  [{i}/{len(cities)}] {city}\n{'='*70}")

        # Step 1: Wongnai bulk
        if not args.skip_wongnai:
            wongnai_out = os.path.join(DATA_DIR, f"wongnai_{city}.csv")
            if os.path.exists(wongnai_out):
                # Check size: if it's already full enough, skip
                with open(wongnai_out, "r", encoding="utf-8") as f:
                    n = sum(1 for _ in f) - 1
                if n >= (args.max_pages * 20) * 0.95:
                    print(f">>> wongnai_{city}: {n} rows already, skipping (use --resume to extend)")
                else:
                    print(f">>> wongnai_{city}: {n} rows present, will RESUME")
                    ok = run([sys.executable,
                              os.path.join(SCRIPT_DIR, "scrape_wongnai.py"),
                              city, "--max-pages", str(args.max_pages),
                              "--delay", str(args.wongnai_delay), "--resume"],
                             f"wongnai {city} (resume)")
                    if not ok:
                        failures.append((city, "wongnai-resume"))
            else:
                ok = run([sys.executable,
                          os.path.join(SCRIPT_DIR, "scrape_wongnai.py"),
                          city, "--max-pages", str(args.max_pages),
                          "--delay", str(args.wongnai_delay)],
                         f"wongnai {city}")
                if not ok:
                    failures.append((city, "wongnai"))

        # Step 2: OSM (only if we have a bbox for the slug)
        if not args.skip_osm:
            osm_out = os.path.join(DATA_DIR, f"osm_{city}.csv")
            if os.path.exists(osm_out):
                print(f">>> osm_{city}: exists, skipping")
            else:
                ok = run([sys.executable,
                          os.path.join(SCRIPT_DIR, "scrape_osm.py"), city],
                         f"osm {city}")
                if not ok:
                    failures.append((city, "osm"))

        # Step 3: merge (only after wongnai + osm both done)
        if not args.skip_merge:
            wongnai_csv = os.path.join(DATA_DIR, f"wongnai_{city}.csv")
            if os.path.exists(wongnai_csv):
                ok = run([sys.executable,
                          os.path.join(SCRIPT_DIR, "merge_hospitality.py"), city],
                         f"merge {city}")
                if not ok:
                    failures.append((city, "merge"))

        # Inter-city cool-off
        if i < len(cities):
            print(f"    cool-off {args.inter_city_delay}s before next city...")
            time.sleep(args.inter_city_delay)

    print(f"\n{'='*70}\n  ORCHESTRATOR DONE\n{'='*70}")
    print(f"Processed {len(cities)} cities. Failures: {len(failures)}")
    for city, step in failures:
        print(f"  - {city}: {step}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
