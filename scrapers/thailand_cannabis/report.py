"""Generate a single-page HTML summary of the Thailand cannabis market scrape.

Reads from data/ files produced by scrape_thaidispos.py, scrape_weed_th.py,
and merge.py. Output: data/report.html.
"""

import csv
import html
import json
import os
import sys
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.thailand_cannabis.common import DATA_DIR  # noqa: E402

REPORT_HTML = os.path.join(DATA_DIR, "report.html")


def load_csv(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def build() -> str:
    licensed = load_csv(os.path.join(DATA_DIR, "thaidispos.csv"))
    listed = load_csv(os.path.join(DATA_DIR, "weed_th.csv"))
    matches = load_csv(os.path.join(DATA_DIR, "matches.csv"))
    with open(os.path.join(DATA_DIR, "summary.json"), "r", encoding="utf-8") as f:
        summary = json.load(f)

    by_city = Counter(r["city"] for r in listed if r.get("city"))
    top_cities = by_city.most_common(20)
    max_city_count = top_cities[0][1] if top_cities else 1

    matched_uuids = {m["listed_uuid"] for m in matches}

    licensed_rows_html = ""
    for r in licensed:
        in_listed = "Yes" if any(
            m["licensed_name"] == r["name"] for m in matches
        ) else "No"
        website = r.get("website") or ""
        website_cell = (
            f'<a href="{esc(website)}" target="_blank" rel="noopener">{esc(website)}</a>'
            if website else "&mdash;"
        )
        rating = r.get("rating") or ""
        reviews = r.get("review_count") or ""
        rating_cell = f"{esc(rating)} ({esc(reviews)} reviews)" if rating else "&mdash;"
        licensed_rows_html += f"""
            <tr>
              <td><strong>{esc(r['name'])}</strong></td>
              <td>{esc(r.get('city'))}</td>
              <td>{esc(r.get('address'))}</td>
              <td>{rating_cell}</td>
              <td>{esc(r.get('opening_hours'))}</td>
              <td>{website_cell}</td>
              <td>{esc(r.get('phone'))}</td>
              <td class="{'badge-ok' if in_listed == 'Yes' else 'badge-warn'}">{in_listed}</td>
            </tr>
        """

    matches_rows_html = ""
    for m in matches:
        matches_rows_html += f"""
            <tr>
              <td>{esc(m['licensed_name'])}</td>
              <td>{esc(m['listed_name'])}</td>
              <td>{esc(m['listed_city'])}</td>
              <td>{esc(m['jaccard'])}</td>
              <td>{esc(m['char_ratio'])}</td>
              <td><a href="{esc(m['listed_url'])}" target="_blank" rel="noopener">view</a></td>
            </tr>
        """

    city_rows_html = ""
    for city, n in top_cities:
        width_pct = round(100 * n / max_city_count, 1)
        city_rows_html += f"""
            <tr>
              <td>{esc(city)}</td>
              <td class="num">{n:,}</td>
              <td><div class="bar" style="width:{width_pct}%"></div></td>
            </tr>
        """

    licensed_in_listed = len(matches)
    total_licensed = summary["licensed_count"]
    total_listed = summary["listed_count"]
    ratio_pct = (100 * licensed_in_listed / total_listed) if total_listed else 0

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Thailand Cannabis Market Snapshot</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
         line-height: 1.55; max-width: 1280px; margin: 0 auto; padding: 24px;
         background: #f7f7f8; color: #1a1a2e; }}
  h1, h2, h3 {{ color: #0d2818; margin-top: 1.8em; }}
  h1 {{ margin-top: 0; }}
  .header {{ background: #0d2818; color: #e6f4ec; padding: 28px 32px;
             border-radius: 10px; margin-bottom: 24px; }}
  .header h1 {{ color: white; margin: 0 0 6px; }}
  .header p {{ margin: 0; opacity: 0.85; font-size: 14px; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 14px; margin: 16px 0 28px; }}
  .stat {{ background: white; padding: 18px 20px; border-radius: 8px;
           box-shadow: 0 1px 2px rgba(0,0,0,.05); border-left: 4px solid #22c55e; }}
  .stat-value {{ font-size: 2.2em; font-weight: 700; color: #0d2818; line-height: 1; }}
  .stat-label {{ font-size: 12px; color: #555; text-transform: uppercase;
                 letter-spacing: 1px; margin-top: 6px; }}
  .stat.warn {{ border-left-color: #f59e0b; }}
  .stat.dim {{ border-left-color: #94a3b8; }}
  .callout {{ background: #fef3c7; border: 1px solid #f59e0b;
              border-radius: 8px; padding: 14px 18px; margin: 16px 0;
              font-size: 14px; }}
  .callout strong {{ color: #92400e; }}
  table {{ width: 100%; border-collapse: collapse; background: white;
           border-radius: 8px; overflow: hidden;
           box-shadow: 0 1px 2px rgba(0,0,0,.05); }}
  th, td {{ padding: 10px 12px; text-align: left;
            border-bottom: 1px solid #eaeaea; font-size: 14px; }}
  th {{ background: #f3f4f6; font-weight: 600; font-size: 12px;
        text-transform: uppercase; letter-spacing: 0.5px; color: #4b5563; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover {{ background: #fafafa; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .badge-ok {{ color: #15803d; font-weight: 600; }}
  .badge-warn {{ color: #b45309; font-weight: 600; }}
  .bar {{ height: 14px; background: linear-gradient(90deg, #22c55e, #16a34a);
          border-radius: 3px; }}
  footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd;
            font-size: 12px; color: #666; }}
  a {{ color: #15803d; }}
</style>
</head>
<body>
  <div class="header">
    <h1>Thailand Cannabis Market &mdash; Two-Tier Snapshot</h1>
    <p>Cross-reference of thaidispos.com (licensed tier) against weed.th (bulk-listed tier). Generated {generated_at}.</p>
  </div>

  <div class="callout">
    <strong>Regulatory context:</strong> Thailand reclassified cannabis as a controlled substance in June 2025.
    All purchases now require a PT 33 medical prescription. The gap between the "licensed" and "listed"
    numbers below reflects this transition &mdash; many listed shops are likely closed, unlicensed,
    or in regulatory limbo. This snapshot does not verify current operating status.
  </div>

  <div class="stats">
    <div class="stat">
      <div class="stat-value">{total_licensed}</div>
      <div class="stat-label">Licensed (thaidispos)</div>
    </div>
    <div class="stat dim">
      <div class="stat-value">{total_listed:,}</div>
      <div class="stat-label">Listed (weed.th)</div>
    </div>
    <div class="stat">
      <div class="stat-value">{licensed_in_listed}/{total_licensed}</div>
      <div class="stat-label">Licensed found in listed</div>
    </div>
    <div class="stat warn">
      <div class="stat-value">{ratio_pct:.2f}%</div>
      <div class="stat-label">Licensed share of listed</div>
    </div>
  </div>

  <h2>Licensed dispensaries ({total_licensed})</h2>
  <p style="color:#555;font-size:13px;margin-top:4px">
    Source: <a href="https://thaidispos.com" target="_blank" rel="noopener">thaidispos.com</a>.
    Site's marketing copy claims 32 dispensaries but only {total_licensed} appear in its public sitemap as of generation date.
  </p>
  <table>
    <thead>
      <tr>
        <th>Name</th><th>City</th><th>Address</th><th>Rating</th>
        <th>Hours</th><th>Website</th><th>Phone</th><th>On weed.th?</th>
      </tr>
    </thead>
    <tbody>{licensed_rows_html}</tbody>
  </table>

  <h2>Cross-reference matches</h2>
  <p style="color:#555;font-size:13px;margin-top:4px">
    Best weed.th match per licensed dispensary using normalized-name Jaccard
    similarity (threshold: 0.4) within matching city.
  </p>
  <table>
    <thead>
      <tr>
        <th>Licensed name</th><th>Best weed.th name</th><th>City</th>
        <th>Jaccard</th><th>Char ratio</th><th>Link</th>
      </tr>
    </thead>
    <tbody>{matches_rows_html}</tbody>
  </table>

  <h2>Listed shops by city (top 20)</h2>
  <p style="color:#555;font-size:13px;margin-top:4px">
    Distribution of the {total_listed:,} shops on weed.th.
    Reflects pre-regulation density &mdash; not all of these are currently open.
  </p>
  <table>
    <thead>
      <tr><th>City</th><th class="num">Shops</th><th>Relative</th></tr>
    </thead>
    <tbody>{city_rows_html}</tbody>
  </table>

  <footer>
    Data files in <code>scrapers/thailand_cannabis/data/</code>:
    thaidispos.csv ({total_licensed} rows),
    weed_th.csv ({total_listed:,} rows),
    merged.csv,
    matches.csv,
    summary.json.
    <br>
    Run order: <code>scrape_thaidispos.py</code> &rarr; <code>scrape_weed_th.py</code>
    &rarr; <code>merge.py</code> &rarr; <code>report.py</code>.
  </footer>
</body>
</html>
"""


def main() -> int:
    html_text = build()
    with open(REPORT_HTML, "w", encoding="utf-8") as f:
        f.write(html_text)
    print(f"[report] wrote {REPORT_HTML}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
