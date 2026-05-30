"""Generate an HTML B2B prospect shortlist for a city's hospitality dataset.

Reads data/hospitality_<slug>.csv produced by merge_hospitality.py.
Output: data/report_hospitality_<slug>.html — sortable table, filterable,
one-click verification links (FB Ad Library, Google Maps).

Usage:
  python report_hospitality.py udonthani --top 50
  python report_hospitality.py udonthani --top 200 --tourism-only
"""

import argparse
import csv
import html
import os
import sys
from datetime import datetime
from urllib.parse import quote

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def gmaps_url(name: str, city: str) -> str:
    return f"https://www.google.com/maps/search/{quote(name + ' ' + city)}"


def render_row(rank: int, r: dict, city: str) -> str:
    name = esc(r.get("name") or r.get("name_en") or r.get("name_thai") or "?")
    qual = esc(r.get("lead_quality", "0"))
    try:
        q = int(qual)
    except ValueError:
        q = 0
    badge_cls = "hi" if q >= 5 else "mid" if q >= 3 else "lo"
    cat = esc(r.get("category_raw") or r.get("subcategory") or "?")
    sources = esc(r.get("sources", ""))
    is_tourism = r.get("is_tourism") == "1"
    fb_count = r.get("fb_ad_count", "")
    fb_count_html = f'<span class="fb-count">{esc(fb_count)}</span>' if fb_count and fb_count != "0" else "&mdash;"

    website = r.get("website") or ""
    website_html = (
        f'<a href="{esc(website)}" target="_blank" rel="noopener">'
        f'{esc(website[:35])}{"..." if len(website) > 35 else ""}</a>'
        if website else "&mdash;"
    )
    phone = esc(r.get("phone") or "") or "&mdash;"

    fb_search = esc(r.get("fb_search_url") or "")
    fb_search_html = f'<a href="{fb_search}" target="_blank" rel="noopener" title="View FB ads">FB Ads</a>' if fb_search else ""
    detail_url = esc(r.get("detail_url") or "")
    detail_html = f'<a href="{detail_url}" target="_blank" rel="noopener">Wongnai</a>' if detail_url else ""
    gmaps_html = f'<a href="{esc(gmaps_url(r.get("name", ""), city))}" target="_blank" rel="noopener">Maps</a>'

    badges = []
    if is_tourism:
        badges.append('<span class="badge badge-tour">tourism</span>')
    if "wongnai+osm" in sources:
        badges.append('<span class="badge badge-both">both srcs</span>')
    elif "osm" == sources:
        badges.append('<span class="badge badge-osm">OSM</span>')

    factors = esc(r.get("score_factors", ""))

    return f"""
    <tr>
      <td class="rank">{rank}</td>
      <td><span class="qbadge q-{badge_cls}">{q}</span></td>
      <td>
        <strong>{name}</strong>
        <div class="meta">{cat} {' '.join(badges)}</div>
        <div class="factors">{factors}</div>
      </td>
      <td class="nowrap">{phone}</td>
      <td>{website_html}</td>
      <td class="nowrap">{fb_count_html}</td>
      <td class="nowrap">{fb_search_html} {detail_html} {gmaps_html}</td>
    </tr>
    """


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slug", help="City slug (e.g. 'udonthani')")
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument("--tourism-only", action="store_true")
    args = parser.parse_args()

    in_path = os.path.join(DATA_DIR, f"hospitality_{args.slug}.csv")
    if not os.path.exists(in_path):
        raise SystemExit(f"Input not found: {in_path}. Run merge_hospitality.py {args.slug} first.")

    with open(in_path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"[report] loaded {len(rows)} rows")

    if args.tourism_only:
        rows = [r for r in rows if r.get("is_tourism") == "1"]
        print(f"[report] tourism-only filter: {len(rows)} rows")

    rows.sort(key=lambda r: -int(r.get("lead_raw") or 0))
    top = rows[: args.top]

    # Stats
    total = len(rows)
    by_q = {}
    for r in rows:
        by_q[r.get("lead_quality", "0")] = by_q.get(r.get("lead_quality", "0"), 0) + 1
    hi_count = sum(by_q.get(str(q), 0) for q in range(5, 11))
    mid_count = sum(by_q.get(str(q), 0) for q in range(3, 5))

    fb_active = sum(1 for r in rows if r.get("fb_ad_count") and r["fb_ad_count"] not in ("", "0"))
    with_phone = sum(1 for r in rows if (r.get("phone") or "").strip())
    with_website_real = sum(1 for r in rows if (r.get("website") or "").startswith("http"))
    tourism = sum(1 for r in rows if r.get("is_tourism") == "1")

    rows_html = "\n".join(render_row(i, r, args.slug) for i, r in enumerate(top, 1))
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    out_html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<title>{esc(args.slug.title())} hospitality B2B prospects (top {len(top)})</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; margin: 0;
         background: #f5f7f5; color: #1a1a2e; line-height: 1.5; font-size: 14px; }}
  .header {{ background: #0d2818; color: #e6f4ec; padding: 22px 28px; }}
  .header h1 {{ margin: 0 0 4px; color: white; font-size: 22px; }}
  .header p {{ margin: 0; opacity: 0.85; font-size: 13px; }}
  .page {{ padding: 22px 24px; max-width: 1480px; margin: 0 auto; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px; margin-bottom: 18px; }}
  .stat {{ background: white; padding: 12px 16px; border-radius: 8px;
           box-shadow: 0 1px 2px rgba(0,0,0,.05); border-left: 4px solid #22c55e; }}
  .stat-val {{ font-size: 1.8em; font-weight: 700; color: #0d2818; line-height: 1; }}
  .stat-lbl {{ font-size: 11px; color: #555; text-transform: uppercase;
               letter-spacing: 0.8px; margin-top: 4px; }}
  .stat.warn {{ border-left-color: #f59e0b; }}
  .stat.dim  {{ border-left-color: #94a3b8; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px;
           overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,.05); }}
  th, td {{ padding: 9px 11px; text-align: left; border-bottom: 1px solid #eaeaea;
            vertical-align: top; }}
  th {{ background: #f3f4f6; font-weight: 600; font-size: 11px;
        text-transform: uppercase; letter-spacing: 0.5px; color: #4b5563; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover {{ background: #fafafa; }}
  td.rank {{ font-weight: 700; color: #94a3b8; }}
  td.nowrap {{ white-space: nowrap; }}
  .qbadge {{ display: inline-block; width: 28px; text-align: center;
             padding: 2px 0; border-radius: 4px; font-weight: 700; font-size: 13px; }}
  .q-hi  {{ background: #dcfce7; color: #14532d; }}
  .q-mid {{ background: #fef3c7; color: #78350f; }}
  .q-lo  {{ background: #f1f5f9; color: #64748b; }}
  .meta {{ font-size: 11px; color: #64748b; margin-top: 2px; }}
  .factors {{ font-size: 10px; color: #94a3b8; margin-top: 1px; font-style: italic; }}
  .badge {{ display: inline-block; padding: 1px 6px; border-radius: 3px;
            font-size: 10px; font-weight: 600; margin-left: 3px; }}
  .badge-tour {{ background: #dbeafe; color: #1e40af; }}
  .badge-osm  {{ background: #fef3c7; color: #78350f; }}
  .badge-both {{ background: #ede9fe; color: #5b21b6; }}
  .fb-count {{ background: #f0fdf4; color: #14532d; padding: 1px 6px; border-radius: 3px;
               font-weight: 600; font-size: 12px; }}
  a {{ color: #15803d; text-decoration: none; margin-right: 6px; }}
  a:hover {{ text-decoration: underline; }}
</style>
</head><body>
  <div class="header">
    <h1>{esc(args.slug.title())} &mdash; hospitality B2B prospects</h1>
    <p>Top {len(top)} of {total:,} unique businesses. Generated {generated}.
       Sources: Wongnai (restaurants/cafés) + OSM (hotels/bars/attractions) + FB Ad Library (ad-spend signal).</p>
  </div>
  <div class="page">
    <div class="stats">
      <div class="stat">
        <div class="stat-val">{total:,}</div>
        <div class="stat-lbl">Total unique</div>
      </div>
      <div class="stat">
        <div class="stat-val">{hi_count}</div>
        <div class="stat-lbl">High quality (5+)</div>
      </div>
      <div class="stat warn">
        <div class="stat-val">{mid_count}</div>
        <div class="stat-lbl">Mid quality (3-4)</div>
      </div>
      <div class="stat">
        <div class="stat-val">{fb_active}</div>
        <div class="stat-lbl">FB ads ≥1</div>
      </div>
      <div class="stat">
        <div class="stat-val">{with_phone}</div>
        <div class="stat-lbl">Phone on file</div>
      </div>
      <div class="stat">
        <div class="stat-val">{with_website_real}</div>
        <div class="stat-lbl">Real website</div>
      </div>
      <div class="stat dim">
        <div class="stat-val">{tourism}</div>
        <div class="stat-lbl">Tourism-relevant cat</div>
      </div>
    </div>
    <table>
      <thead><tr>
        <th>#</th><th>Score</th><th>Shop</th>
        <th>Phone</th><th>Website</th>
        <th title="FB ads count">FB ads</th>
        <th>Verify</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    <p style="font-size:12px;color:#64748b;margin-top:18px">
      Score 0-10. Built from: real website (+3), FB ads in 1-100 range (+3),
      tourism category (+2), phone (+2), email (+1), reviews log-scaled (+3 cap).
      Will improve dramatically once Wongnai unbans (phone+hours+cuisine for all 1,144)
      and/or Google Places enrichment runs (website+phone+GBP claim for all 1,144).
    </p>
  </div>
</body></html>
"""

    suffix = "_tourism" if args.tourism_only else ""
    out_path = os.path.join(DATA_DIR, f"report_hospitality_{args.slug}{suffix}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out_html)
    print(f"[report] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
