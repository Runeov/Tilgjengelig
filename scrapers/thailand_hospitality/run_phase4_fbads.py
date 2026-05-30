"""Phase 4 orchestrator: FB Ad Library check for each city's top-N shops.

Calls check_fb_ads.py for each city. Same pacing strategy as Phase 3.

Usage:
  python run_phase4_fbads.py
  python run_phase4_fbads.py --top 300
"""

import argparse
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")


def cities_with_data() -> list[str]:
    out = []
    for fn in sorted(os.listdir(DATA_DIR)):
        if fn.startswith("wongnai_") and fn.endswith(".csv") \
                and "_detailed" not in fn and "_google" not in fn \
                and "_contacts_" not in fn:
            slug = fn[len("wongnai_"):-len(".csv")]
            if slug in ("", "country"):
                continue
            out.append(slug)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cities", help="Comma-separated city slugs")
    parser.add_argument("--top", type=int, default=500)
    parser.add_argument("--inter-city-delay", type=int, default=60)
    args = parser.parse_args()

    if args.cities:
        cities = [c.strip() for c in args.cities.split(",") if c.strip()]
    else:
        cities = cities_with_data()
    print(f"[phase4] {len(cities)} cities: {', '.join(cities)}")
    print(f"[phase4] top {args.top} food shops/city")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    failures = []
    for i, city in enumerate(cities, 1):
        cmd = [sys.executable,
               os.path.join(SCRIPT_DIR, "check_fb_ads.py"),
               city, "--food-only", "--limit", str(args.top), "--resume"]
        print(f"\n{'='*70}\n  [{i}/{len(cities)}] {city}\n{'='*70}")
        print(f"  cmd: {' '.join(cmd)}")
        t0 = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                              encoding="utf-8", errors="replace")
        elapsed = time.time() - t0
        ok = proc.returncode == 0
        for line in (proc.stdout or "").strip().splitlines()[-3:]:
            print(f"    {line}")
        print(f"  [{city}] {'DONE' if ok else 'FAILED'} in {elapsed:.0f}s")
        if not ok:
            failures.append(city)
            for line in (proc.stderr or "").strip().splitlines()[-3:]:
                print(f"    ! {line}")
        if i < len(cities):
            print(f"    cool-off {args.inter_city_delay}s...")
            time.sleep(args.inter_city_delay)

    print(f"\nPhase 4 done. Failures: {len(failures)}: {failures}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
