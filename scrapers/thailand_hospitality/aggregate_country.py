"""Aggregate per-city hospitality CSVs into a country-wide reachable contact list.

Reads every data/hospitality_<city>.csv, dedupes by (name, lat, lng) across cities,
and writes:
  - data/hospitality_country.csv         — all unique businesses with score + city
  - data/reachable_country.csv           — subset with at least one contact channel
                                            (phone OR email OR fb_search_url OR detail_url)
  - data/report_hospitality_country.html — top-200 prospects across the whole country

Usage:
  python aggregate_country.py
  python aggregate_country.py --top 500       # bigger HTML report
  python aggregate_country.py --tourism-only  # filter to tourism-relevant categories
"""

import argparse
import csv
import html
import math
import os
import sys
from collections import Counter
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def collect_per_city() -> list[dict]:
    """Read every hospitality_<city>.csv in data/."""
    files = sorted(
        f for f in os.listdir(DATA_DIR)
        if f.startswith("hospitality_") and f.endswith(".csv")
        and "_country" not in f
    )
    print(f"[agg] {len(files)} per-city files: {files}")
    rows = []
    for fn in files:
        city = fn[len("hospitality_"):-len(".csv")]
        with open(os.path.join(DATA_DIR, fn), "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                r["_city_slug"] = city
                rows.append(r)
    return rows


def dedupe_across_cities(rows: list[dict]) -> list[dict]:
    """A business that appears in two adjacent cities' bboxes might be duplicated.
    Dedup by src_id (already unique within source) AND by (normalized name, geo cell)."""
    seen: set = set()
    out: list[dict] = []
    for r in rows:
        sid = r.get("src_id") or ""
        if sid and sid in seen:
            continue
        seen.add(sid)
        # Secondary check: (name, lat, lng rounded)
        name = (r.get("name") or "").strip().lower()
        try:
            lat = round(float(r.get("lat") or 0), 4)
            lng = round(float(r.get("lng") or 0), 4)
        except (TypeError, ValueError):
            lat = lng = 0
        geo_key = (name, lat, lng) if name else None
        if geo_key and geo_key in seen:
            continue
        if geo_key:
            seen.add(geo_key)
        out.append(r)
    return out


def has_contact(r: dict) -> bool:
    """Reachable = has at least one contact channel."""
    return bool(
        (r.get("phone") or "").strip()
        or (r.get("email") or "").strip()
        or (r.get("fb_search_url") or "").strip()
        or (r.get("detail_url") or "").strip()  # Wongnai URL = can DM via Wongnai or click-through
    )


def render_html(rows: list[dict], top: int, tourism_only: bool) -> str:
    if tourism_only:
        rows = [r for r in rows if r.get("is_tourism") == "1"]
    rows.sort(key=lambda r: -int(r.get("lead_raw") or 0))
    shown = rows[:top]
    total = len(rows)

    # Stats
    reachable = sum(1 for r in rows if has_contact(r))
    with_phone = sum(1 for r in rows if (r.get("phone") or "").strip())
    fb_active = sum(1 for r in rows if r.get("fb_ad_count") and r["fb_ad_count"] not in ("", "0"))
    by_city = Counter(r.get("_city_slug", "?") for r in rows)
    by_q = Counter(r.get("lead_quality", "0") for r in rows)
    hi_count = sum(by_q.get(str(q), 0) for q in range(5, 11))

    rows_html = ""
    for i, r in enumerate(shown, 1):
        name = esc(r.get("name") or "?")
        cat = esc(r.get("category_raw") or r.get("subcategory") or "?")
        city = esc(r.get("_city_slug") or "?")
        phone = esc(r.get("phone") or "") or "&mdash;"
        website = r.get("website") or ""
        if website:
            site_html = (f'<a href="{esc(website)}" target="_blank" rel="noopener">'
                         f'{esc(website[:35])}{"..." if len(website) > 35 else ""}</a>')
        else:
            site_html = "&mdash;"
        fb = r.get("fb_ad_count") or ""
        fb_html = f'<span class="fb-cnt">{esc(fb)}</span>' if fb and fb != "0" else "&mdash;"
        try:
            q = int(r.get("lead_quality", "0"))
        except ValueError:
            q = 0
        q_cls = "hi" if q >= 5 else "mid" if q >= 3 else "lo"
        detail_url = r.get("detail_url") or r.get("fb_search_url") or ""
        link_html = (f'<a href="{esc(detail_url)}" target="_blank" rel="noopener">link</a>'
                     if detail_url else "&mdash;")
        rows_html += f"""
        <tr>
          <td class="rank">{i}</td>
          <td><span class="qbadge q-{q_cls}">{q}</span></td>
          <td><strong>{name}</strong><div class="meta">{cat}</div></td>
          <td>{city}</td>
          <td class="nowrap">{phone}</td>
          <td>{site_html}</td>
          <td class="nowrap">{fb_html}</td>
          <td class="nowrap">{link_html}</td>
        </tr>
        """

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    cities_table = ""
    for city, n in by_city.most_common():
        cities_table += f"<tr><td>{esc(city)}</td><td class='num'>{n:,}</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<title>Thailand hospitality — country B2B prospects</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; margin: 0;
         background: #f5f7f5; color: #1a1a2e; font-size: 14px; line-height: 1.5; }}
  .header {{ background: #0d2818; color: #e6f4ec; padding: 22px 28px; }}
  .header h1 {{ margin: 0 0 4px; color: white; font-size: 22px; }}
  .header p  {{ margin: 0; opacity: 0.85; font-size: 13px; }}
  .page {{ padding: 22px 24px; max-width: 1500px; margin: 0 auto; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px; margin-bottom: 18px; }}
  .stat {{ background: white; padding: 12px 16px; border-radius: 8px;
           box-shadow: 0 1px 2px rgba(0,0,0,.05); border-left: 4px solid #22c55e; }}
  .stat-val {{ font-size: 1.8em; font-weight: 700; line-height: 1; color: #0d2818; }}
  .stat-lbl {{ font-size: 11px; color: #555; text-transform: uppercase;
               letter-spacing: 0.8px; margin-top: 4px; }}
  .stat.warn {{ border-left-color: #f59e0b; }}
  .stat.dim  {{ border-left-color: #94a3b8; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px;
           overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,.05); }}
  th, td {{ padding: 8px 11px; text-align: left; border-bottom: 1px solid #eaeaea; }}
  th {{ background: #f3f4f6; font-weight: 600; font-size: 11px;
        text-transform: uppercase; letter-spacing: 0.5px; color: #4b5563; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover {{ background: #fafafa; }}
  td.rank {{ font-weight: 700; color: #94a3b8; }}
  td.nowrap {{ white-space: nowrap; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .qbadge {{ display: inline-block; width: 28px; text-align: center;
             padding: 2px 0; border-radius: 4px; font-weight: 700; font-size: 13px; }}
  .q-hi {{ background: #dcfce7; color: #14532d; }}
  .q-mid {{ background: #fef3c7; color: #78350f; }}
  .q-lo {{ background: #f1f5f9; color: #64748b; }}
  .meta {{ font-size: 11px; color: #64748b; margin-top: 2px; }}
  .fb-cnt {{ background: #f0fdf4; color: #14532d; padding: 1px 6px; border-radius: 3px;
             font-weight: 600; font-size: 12px; }}
  a {{ color: #15803d; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .twocol {{ display: grid; grid-template-columns: 1fr 280px; gap: 16px; }}
  .sidebar table {{ font-size: 12px; }}
</style>
</head><body>
  <div class="header">
    <h1>Thailand hospitality &mdash; country-wide B2B prospects</h1>
    <p>{total:,} unique businesses across {len(by_city)} cities. {reachable:,} reachable
       (have phone or contactable URL). Top {len(shown)} shown. Generated {generated}.</p>
  </div>
  <div class="page">
    <div class="stats">
      <div class="stat"><div class="stat-val">{total:,}</div><div class="stat-lbl">Total unique</div></div>
      <div class="stat"><div class="stat-val">{reachable:,}</div><div class="stat-lbl">Reachable</div></div>
      <div class="stat"><div class="stat-val">{with_phone:,}</div><div class="stat-lbl">Phone on file</div></div>
      <div class="stat warn"><div class="stat-val">{hi_count:,}</div><div class="stat-lbl">Score 5+</div></div>
      <div class="stat"><div class="stat-val">{fb_active:,}</div><div class="stat-lbl">FB ads ≥1</div></div>
      <div class="stat dim"><div class="stat-val">{len(by_city)}</div><div class="stat-lbl">Cities</div></div>
    </div>

    <div class="twocol">
      <div>
        <table>
          <thead><tr>
            <th>#</th><th>Score</th><th>Shop</th><th>City</th>
            <th>Phone</th><th>Website</th><th>FB ads</th><th>Link</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
      </div>
      <aside class="sidebar">
        <h3 style="margin-top:0;font-size:14px">Per-city counts</h3>
        <table>{cities_table}</table>
      </aside>
    </div>
  </div>
</body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--top", type=int, default=200)
    parser.add_argument("--tourism-only", action="store_true")
    args = parser.parse_args()

    rows = collect_per_city()
    print(f"[agg] total raw rows: {len(rows):,}")
    rows = dedupe_across_cities(rows)
    print(f"[agg] after cross-city dedupe: {len(rows):,}")

    # Country CSV
    if rows:
        fieldnames = list(rows[0].keys())
        out_path = os.path.join(DATA_DIR, "hospitality_country.csv")
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow({k: r.get(k, "") for k in fieldnames})
        print(f"[agg] wrote {out_path}")

    # Reachable subset
    reachable = [r for r in rows if has_contact(r)]
    reach_path = os.path.join(DATA_DIR, "reachable_country.csv")
    if reachable:
        with open(reach_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in reachable:
                writer.writerow({k: r.get(k, "") for k in fieldnames})
        print(f"[agg] wrote {reach_path} ({len(reachable):,} rows)")

    # HTML
    html_out = render_html(rows, args.top, args.tourism_only)
    html_path = os.path.join(DATA_DIR,
                             "report_hospitality_country" + ("_tourism" if args.tourism_only else "") + ".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"[agg] wrote {html_path}")

    # Stats summary
    print(f"\nTotal: {len(rows):,}  Reachable: {len(reachable):,}")
    by_city = Counter(r.get("_city_slug", "?") for r in rows)
    print(f"Top 10 cities by row count:")
    for city, n in by_city.most_common(10):
        print(f"  {n:>5}  {city}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
