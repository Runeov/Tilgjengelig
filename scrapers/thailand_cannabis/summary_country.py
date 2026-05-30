"""Quick country-wide summary of the Google-enriched weed.th data.

Reads data/weed_th_google.csv (the country scrape output) and prints per-city
totals: shops scraped, high-confidence Google matches, phones recovered,
websites recovered. Optionally writes an HTML summary page.

Usage:
  python summary_country.py                # print to console
  python summary_country.py --html         # also write data/report_country.html
  python summary_country.py --top 30       # only show top 30 cities by shop count
"""

import argparse
import csv
import html
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.thailand_cannabis.common import DATA_DIR  # noqa: E402
from scrapers.thailand_cannabis.city_normalize import canonical_city  # noqa: E402

COUNTRY_CSV = os.path.join(DATA_DIR, "weed_th_google.csv")
REPORT_HTML = os.path.join(DATA_DIR, "report_country.html")


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--html", action="store_true", help="Also write report_country.html")
    parser.add_argument("--top", type=int, default=None, help="Only show top N cities (default: all)")
    parser.add_argument("--raw", action="store_true",
                        help="Skip city normalization (show weed.th's raw city values; "
                             "results in 107 buckets instead of ~77 canonical provinces)")
    parser.add_argument("--sort", choices=["shops", "phones"], default="shops",
                        help="Sort rows by (default: shops)")
    args = parser.parse_args()

    if not os.path.exists(COUNTRY_CSV):
        print(f"ERROR: {COUNTRY_CSV} not found. Run enrich_google_places.py on weed_th.csv first.",
              file=sys.stderr)
        return 1

    # Aggregate per city (canonical by default; --raw to keep weed.th's exact values)
    by_city: dict[str, dict[str, int]] = defaultdict(lambda: {
        "total": 0, "high": 0, "medium": 0, "low": 0, "no_result": 0,
        "phones": 0, "websites": 0, "hours": 0,
    })
    grand_total = 0
    with open(COUNTRY_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            raw_city = r.get("city") or ""
            city = raw_city.strip() if args.raw else canonical_city(raw_city)
            if not city:
                city = "(unknown)"
            stats = by_city[city]
            stats["total"] += 1
            conf = (r.get("google_match_confidence") or "").strip()
            if conf in ("high", "medium", "low", "no_result"):
                stats[conf] += 1
            if r.get("google_phone"):
                stats["phones"] += 1
            if r.get("google_website"):
                stats["websites"] += 1
            if r.get("google_hours"):
                stats["hours"] += 1
            grand_total += 1

    sort_key = "phones" if args.sort == "phones" else "total"
    rows = sorted(by_city.items(), key=lambda kv: -kv[1][sort_key])
    shown = rows[: args.top] if args.top else rows

    # Console table
    print(f"\n{'CITY':<28}{'SHOPS':>7}{'HIGH':>7}{'MED':>5}{'LOW':>5}{'NONE':>6}{'PHONES':>8}{'WEB':>6}")
    print("-" * 76)
    # Country-wide totals (over ALL rows, not just shown ones)
    country_totals = {"total": 0, "high": 0, "medium": 0, "low": 0, "no_result": 0, "phones": 0, "websites": 0}
    for _, s in rows:
        for k in country_totals:
            country_totals[k] += s[k]
    # Shown-only totals (just for the footer of the displayed slice)
    shown_totals = {k: 0 for k in country_totals}
    for city, s in shown:
        print(f"{city[:27]:<28}{s['total']:>7}{s['high']:>7}{s['medium']:>5}{s['low']:>5}"
              f"{s['no_result']:>6}{s['phones']:>8}{s['websites']:>6}")
        for k in shown_totals:
            shown_totals[k] += s[k]
    print("-" * 76)
    print(f"{'TOTAL (shown):':<28}{shown_totals['total']:>7}{shown_totals['high']:>7}"
          f"{shown_totals['medium']:>5}{shown_totals['low']:>5}{shown_totals['no_result']:>6}"
          f"{shown_totals['phones']:>8}{shown_totals['websites']:>6}")
    if args.top and len(rows) > len(shown):
        print(f"({country_totals['total'] - shown_totals['total']:,} shops in "
              f"{len(rows) - len(shown)} more cities not shown)")
    print()
    if country_totals['total']:
        denom = country_totals['total']
        pct = lambda n: f"{100*n/denom:.1f}%"
        mode = "(weed.th raw cities)" if args.raw else "(canonical provinces)"
        print(f"  Country-wide totals {mode}, denom={denom:,}:")
        print(f"  Phones recovered:    {country_totals['phones']:>6,} ({pct(country_totals['phones'])})")
        print(f"  Websites recovered:  {country_totals['websites']:>6,} ({pct(country_totals['websites'])})")
        print(f"  High-conf matches:   {country_totals['high']:>6,} ({pct(country_totals['high'])})")
        print(f"  Google no_result:    {country_totals['no_result']:>6,} ({pct(country_totals['no_result'])})")
        print(f"  Cities/buckets:      {len(rows)}")
    # For the HTML below, alias the country totals as `totals` so existing code works.
    totals = country_totals

    if not args.html:
        return 0

    # HTML summary
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    table_rows = ""
    for city, s in rows:
        safe = city.lower().replace(" ", "_")
        link = f'<a href="report_{esc(safe)}.html">{esc(city)}</a>'
        phone_pct = (100 * s["phones"] / s["total"]) if s["total"] else 0
        table_rows += f"""
            <tr>
              <td>{link}</td>
              <td class="num">{s['total']:,}</td>
              <td class="num">{s['high']:,}</td>
              <td class="num dim">{s['medium']:,}</td>
              <td class="num dim">{s['low']:,}</td>
              <td class="num">{s['phones']:,}</td>
              <td class="num">{phone_pct:.0f}%</td>
              <td class="num">{s['websites']:,}</td>
            </tr>
        """

    grand_phone_pct = (100 * totals['phones'] / grand_total) if grand_total else 0
    html_out = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<title>Thailand cannabis &mdash; country summary</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
         max-width: 1200px; margin: 0 auto; padding: 24px; background: #f7f7f8;
         color: #1a1a2e; line-height: 1.5; }}
  .header {{ background: #0d2818; color: #e6f4ec; padding: 24px 28px;
             border-radius: 10px; margin-bottom: 20px; }}
  .header h1 {{ margin: 0 0 6px; color: white; }}
  .header p {{ margin: 0; opacity: 0.85; font-size: 14px; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px; margin-bottom: 22px; }}
  .stat {{ background: white; padding: 16px 18px; border-radius: 8px;
           box-shadow: 0 1px 2px rgba(0,0,0,.05); border-left: 4px solid #22c55e; }}
  .stat-value {{ font-size: 1.9em; font-weight: 700; line-height: 1; color: #0d2818; }}
  .stat-label {{ font-size: 11px; color: #555; text-transform: uppercase;
                 letter-spacing: 0.8px; margin-top: 5px; }}
  table {{ width: 100%; border-collapse: collapse; background: white;
           border-radius: 8px; overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,.05);
           font-size: 14px; }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #eaeaea; }}
  th {{ background: #f3f4f6; font-weight: 600; font-size: 11px;
        text-transform: uppercase; letter-spacing: 0.5px; color: #4b5563; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover {{ background: #fafafa; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.dim {{ color: #94a3b8; }}
  a {{ color: #15803d; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style>
</head><body>
  <div class="header">
    <h1>Thailand cannabis market &mdash; country summary</h1>
    <p>Source: weed.th sitemap (11,271 shops) + Google Places enrichment. Generated {generated_at}.</p>
  </div>
  <div class="stats">
    <div class="stat">
      <div class="stat-value">{grand_total:,}</div>
      <div class="stat-label">Total shops</div>
    </div>
    <div class="stat">
      <div class="stat-value">{totals['phones']:,}</div>
      <div class="stat-label">Phones recovered ({grand_phone_pct:.0f}%)</div>
    </div>
    <div class="stat">
      <div class="stat-value">{totals['high']:,}</div>
      <div class="stat-label">High-confidence matches</div>
    </div>
    <div class="stat">
      <div class="stat-value">{len(rows)}</div>
      <div class="stat-label">Cities covered</div>
    </div>
  </div>
  <p style="font-size:13px;color:#555;margin:18px 0 8px">
    City names link to per-city reports if they've been generated. Run
    <code>python scrapers/thailand_cannabis/report_city.py "&lt;City Name&gt;"</code>
    for any city to build its interactive directory.
  </p>
  <table>
    <thead><tr>
      <th>City</th><th class="num">Shops</th>
      <th class="num">High</th><th class="num">Med</th><th class="num">Low</th>
      <th class="num">Phones</th><th class="num">Phone %</th>
      <th class="num">Websites</th>
    </tr></thead>
    <tbody>{table_rows}</tbody>
  </table>
</body></html>
"""
    with open(REPORT_HTML, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"\nWrote {REPORT_HTML}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
