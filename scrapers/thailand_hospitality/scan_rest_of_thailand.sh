#!/usr/bin/env bash
#
# One-shot: scan the rest of Thailand (39 not-yet-covered provinces) for
# hospitality incl. bars & shows, then aggregate into country-wide files.
#
# Run from a machine / session with open network egress to:
#   overpass-api.de, nominatim.openstreetmap.org, www.wongnai.com
#
# Usage:
#   ./scan_rest_of_thailand.sh
#
# Tunable via env vars (defaults are rate-limit-safe for Wongnai):
#   MAX_PAGES=50          Wongnai pages per province (~20 shops/page)
#   WONGNAI_DELAY=15      seconds between Wongnai page fetches
#   INTER_CITY_DELAY=60   cool-off seconds between provinces
#   PASSES=3              resume passes (each skips already-done provinces)
#   LIMIT=                only process the next N provinces (e.g. LIMIT=8 for one batch)
#   SKIP_WONGNAI=1        OSM bars+shows only (fast, no 403 risk)
#   PYTHON=python3        interpreter to use
#
# Resume-safe: a province with data/hospitality_<slug>.csv is skipped, so you can
# Ctrl-C and re-run anytime. Wongnai IP-bans after ~80 req/2min; the 15s delay
# keeps you under that — raise WONGNAI_DELAY if you still get 403s.

set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
MAX_PAGES="${MAX_PAGES:-50}"
WONGNAI_DELAY="${WONGNAI_DELAY:-15}"
INTER_CITY_DELAY="${INTER_CITY_DELAY:-60}"
PASSES="${PASSES:-3}"

# Optional passthrough flags
EXTRA=()
[ -n "${LIMIT:-}" ] && EXTRA+=(--limit "$LIMIT")
[ -n "${SKIP_WONGNAI:-}" ] && EXTRA+=(--skip-wongnai)

echo "============================================================"
echo "  Scan rest of Thailand — hospitality (bars & shows)"
echo "  max-pages=$MAX_PAGES  wongnai-delay=${WONGNAI_DELAY}s"
echo "  inter-city-delay=${INTER_CITY_DELAY}s  passes=$PASSES"
[ ${#EXTRA[@]} -gt 0 ] && echo "  extra: ${EXTRA[*]}"
echo "============================================================"

# 1. Dependencies
if ! "$PY" -c "import requests" 2>/dev/null; then
  echo "[deps] installing requirements..."
  "$PY" -m pip install -r ../../requirements.txt
fi

# 2. Network preflight (aborts early if hosts are blocked)
if ! "$PY" run_remaining_provinces.py --check; then
  echo "[abort] data sources unreachable — fix the network policy / allowlist first."
  exit 2
fi

# 3. Show what's left
"$PY" run_remaining_provinces.py --list | head -1

# 4. Scrape in resume passes (each pass retries provinces that failed before)
for p in $(seq 1 "$PASSES"); do
  echo ""
  echo ">>> Scrape pass $p/$PASSES"
  if "$PY" run_remaining_provinces.py \
        --max-pages "$MAX_PAGES" \
        --wongnai-delay "$WONGNAI_DELAY" \
        --inter-city-delay "$INTER_CITY_DELAY" \
        --no-preflight \
        "${EXTRA[@]}"; then
    echo ">>> Pass $p completed with no failures."
    break
  fi
  if [ "$p" -lt "$PASSES" ]; then
    echo ">>> Pass $p had failures (likely transient/Wongnai 403). Cooling off 120s, then retrying remaining..."
    sleep 120
  else
    echo ">>> Reached final pass with some failures still remaining (see log above)."
  fi
done

# 5. Aggregate into country-wide files + HTML report
echo ""
echo ">>> Aggregating country-wide..."
"$PY" aggregate_country.py
"$PY" finalize_country.py

echo ""
echo "============================================================"
echo "  DONE. Outputs in data/:"
echo "    hospitality_country.csv        all unique businesses (+ venue_type)"
echo "    reachable_country*.csv         contactable subset"
echo "    contact_list_country.csv       outreach-ready"
echo "    report_hospitality_country.html"
echo ""
echo "  Bars only:  awk -F, 'NR==1||\$0~/,bar,/' data/hospitality_country.csv"
echo "  Shows only: awk -F, 'NR==1||\$0~/,show,/' data/hospitality_country.csv"
echo "============================================================"
