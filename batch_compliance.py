#!/usr/bin/env python3
"""
Batch Compliance Scanner for Norwegian Counties.

Runs legal compliance checks (Åpenhetsloven, Cookies, CSRD, EAA) on all
organizations from per-county CSVs. Designed to run separately alongside
the WCAG batch scanner.

Usage:
    python batch_compliance.py                          # Scan all counties
    python batch_compliance.py --county Finnmark        # Scan specific county
    python batch_compliance.py --no-browser             # Static HTML only
    python batch_compliance.py --resume                 # Resume interrupted scan
"""

import argparse
import csv
import glob
import json
import os
import re
import sys
import time
from dataclasses import asdict
from datetime import datetime
from urllib.parse import urlparse

from compliance_checker import ComplianceChecker, generate_compliance_html

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIRKSOMHETER_DIR = os.path.join(SCRIPT_DIR, "Virksomheter")
REPORTS_DIR = os.path.join(SCRIPT_DIR, "reports", "compliance")


def sanitize_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', '_', name)
    return name.strip('_')[:50].lower()


def find_county_csvs(virksomheter_dir, county_filter=None):
    pattern = os.path.join(virksomheter_dir, "*Public.csv")
    files = glob.glob(pattern)
    files = [f for f in files if 'komplett' not in f.lower()]

    if county_filter:
        filter_lower = county_filter.lower()
        files = [f for f in files if filter_lower in os.path.basename(f).lower()]

    # Oslo last (largest)
    def _sort_key(f):
        name = os.path.basename(f).lower()
        if name.startswith('oslo'):
            return (1, name)
        return (0, name)

    return sorted(files, key=_sort_key)


def extract_urls_from_csv(csv_file):
    companies = []
    seen_urls = set()

    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get('Offisiell nettside', '').strip()
            name = row.get('Virksomhet', '').strip()

            if not url or not url.startswith('http'):
                continue

            url_key = url.rstrip('/').lower()
            if url_key in seen_urls:
                continue

            seen_urls.add(url_key)
            companies.append({
                'name': name or urlparse(url).netloc,
                'url': url,
                'kommune': row.get('Kommunenavn', ''),
                'org_nr': row.get('Org nummer', ''),
            })

    return companies


def scan_county(county_csv, checker, reports_dir, resume_data):
    """Run compliance checks on all orgs in a county CSV."""
    basename = os.path.basename(county_csv)
    county_name = basename.replace('Public.csv', '').strip()

    companies = extract_urls_from_csv(county_csv)

    print(f"\n{'#' * 60}")
    print(f"# {county_name}: {len(companies)} organizations with URLs")
    print(f"{'#' * 60}")

    # Check if already done (resume)
    if resume_data and county_name in resume_data:
        existing = resume_data[county_name]
        print(f"  Resuming: {len(existing)} already scanned")
        return existing, county_name

    county_dir = os.path.join(reports_dir, sanitize_filename(county_name))
    os.makedirs(county_dir, exist_ok=True)

    results = []

    for i, company in enumerate(companies, 1):
        url = company['url']
        name = company['name']

        print(f"\n  [{i}/{len(companies)}]")
        print(f"  {'='*56}")
        print(f"  {name}")
        print(f"  {url}")
        print(f"  {'='*56}")

        result_data = {
            'name': name,
            'url': url,
            'kommune': company['kommune'],
            'org_nr': company['org_nr'],
            'status': 'error',
            'total_checks': 0,
            'passed': 0,
            'failed': 0,
            'score_pct': 0,
            'checks': [],
        }

        try:
            result = checker.check_site(url)

            if result.error:
                print(f"  -> Error: {result.error}")
                result_data['error'] = result.error
            else:
                summary = result.summary
                result_data['status'] = 'success'
                result_data['total_checks'] = summary['total_checks']
                result_data['passed'] = summary['passed']
                result_data['failed'] = summary['failed']
                result_data['score_pct'] = summary['score_pct']
                result_data['by_module'] = summary['by_module']
                result_data['checks'] = [asdict(c) for c in result.checks]

                # Save individual HTML report
                report_name = f"compliance_{sanitize_filename(name)}.html"
                report_path = os.path.join(county_dir, report_name)
                generate_compliance_html(result, report_path)
                result_data['report_file'] = report_path

                print(f"  -> Score: {summary['score_pct']}% ({summary['passed']}/{summary['total_checks']} passed)")

        except Exception as e:
            print(f"  -> Error: {e}")
            result_data['error'] = str(e)

        results.append(result_data)

    return results, county_name


def generate_county_compliance_html(county_name, results, output_file):
    """Generate summary HTML for a county's compliance results."""
    total = len(results)
    successful = sum(1 for r in results if r.get('status') == 'success')
    avg_score = 0
    if successful:
        avg_score = round(sum(r.get('score_pct', 0) for r in results if r.get('status') == 'success') / successful)

    # Module-level stats
    module_stats = {}
    for r in results:
        for check in r.get('checks', []):
            mod = check.get('module', 'Unknown')
            if mod not in module_stats:
                module_stats[mod] = {'passed': 0, 'failed': 0}
            if check.get('passed'):
                module_stats[mod]['passed'] += 1
            else:
                module_stats[mod]['failed'] += 1

    score_color = "#4caf50" if avg_score >= 60 else ("#ff9800" if avg_score >= 35 else "#f44336")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="no">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Compliance: {county_name}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
  h1 {{ font-size: 1.5rem; color: #1a237e; margin-bottom: 4px; }}
  .subtitle {{ color: #666; font-size: 0.9rem; margin-bottom: 20px; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }}
  .stat {{ background: white; border-radius: 10px; padding: 16px; text-align: center; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }}
  .stat .value {{ font-size: 1.8rem; font-weight: 700; }}
  .stat .label {{ font-size: 0.8rem; color: #888; }}
  .stat .value.green {{ color: #2e7d32; }}
  .stat .value.orange {{ color: #e65100; }}
  .stat .value.red {{ color: #c62828; }}
  .modules {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 20px; }}
  .mod-card {{ background: white; border-radius: 10px; padding: 16px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }}
  .mod-card h3 {{ font-size: 0.9rem; color: #1a237e; margin-bottom: 8px; }}
  .mod-bar {{ height: 8px; background: #eee; border-radius: 4px; overflow: hidden; }}
  .mod-bar-fill {{ height: 100%; border-radius: 4px; }}
  .mod-bar-fill.good {{ background: #4caf50; }}
  .mod-bar-fill.warn {{ background: #ff9800; }}
  .mod-bar-fill.bad {{ background: #f44336; }}
  .mod-stat {{ font-size: 0.8rem; color: #666; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }}
  th {{ background: #1a237e; color: white; padding: 10px 12px; text-align: left; font-size: 0.85rem; font-weight: 600; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0; font-size: 0.85rem; }}
  tr:hover {{ background: #f8f9ff; }}
  .score-badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.8rem; font-weight: 600; }}
  .score-badge.good {{ background: #e8f5e9; color: #2e7d32; }}
  .score-badge.warn {{ background: #fff3e0; color: #e65100; }}
  .score-badge.bad {{ background: #ffebee; color: #c62828; }}
  a {{ color: #1a237e; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .footer {{ text-align: center; color: #999; font-size: 0.8rem; margin-top: 24px; padding: 16px; }}
</style>
</head>
<body>
<div class="container">
  <h1>Compliance Audit: {county_name}</h1>
  <p class="subtitle">{total} virksomheter skannet &mdash; {timestamp}</p>

  <div class="stats">
    <div class="stat">
      <div class="value" style="color:{score_color}">{avg_score}%</div>
      <div class="label">Gjennomsnittlig score</div>
    </div>
    <div class="stat">
      <div class="value">{total}</div>
      <div class="label">Virksomheter</div>
    </div>
    <div class="stat">
      <div class="value green">{sum(1 for r in results if r.get('score_pct',0) >= 60)}</div>
      <div class="label">Score &ge; 60%</div>
    </div>
    <div class="stat">
      <div class="value red">{sum(1 for r in results if r.get('score_pct',0) < 30 and r.get('status')=='success')}</div>
      <div class="label">Score &lt; 30%</div>
    </div>
  </div>

  <div class="modules">
"""

    for mod, stats in sorted(module_stats.items()):
        mod_total = stats['passed'] + stats['failed']
        mod_pct = round(stats['passed'] / mod_total * 100) if mod_total else 0
        bar_class = "good" if mod_pct >= 60 else ("warn" if mod_pct >= 35 else "bad")
        html += f"""
    <div class="mod-card">
      <h3>{mod}</h3>
      <div class="mod-bar"><div class="mod-bar-fill {bar_class}" style="width:{mod_pct}%"></div></div>
      <div class="mod-stat">{stats['passed']}/{mod_total} bestått ({mod_pct}%)</div>
    </div>
"""

    html += """
  </div>

  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Virksomhet</th>
        <th>Kommune</th>
        <th>Score</th>
        <th>Åpenhetsloven</th>
        <th>Cookies</th>
        <th>CSRD</th>
        <th>EAA</th>
        <th>Rapport</th>
      </tr>
    </thead>
    <tbody>
"""

    sorted_results = sorted(results, key=lambda x: x.get('score_pct', 0))

    for i, r in enumerate(sorted_results, 1):
        score = r.get('score_pct', 0)
        score_class = "good" if score >= 60 else ("warn" if score >= 35 else "bad")

        # Per-module pass counts
        mod_scores = {}
        for check in r.get('checks', []):
            mod = check.get('module', '')
            if mod not in mod_scores:
                mod_scores[mod] = [0, 0]
            mod_scores[mod][1] += 1
            if check.get('passed'):
                mod_scores[mod][0] += 1

        def mod_cell(mod_name):
            for mod, (p, t) in mod_scores.items():
                if mod_name.lower() in mod.lower():
                    pct = round(p / t * 100) if t else 0
                    cls = "good" if pct >= 60 else ("warn" if pct >= 35 else "bad")
                    return f'<span class="score-badge {cls}">{p}/{t}</span>'
            return '<span style="color:#ccc">-</span>'

        report_link = ""
        if r.get('report_file'):
            report_link = f'<a href="{os.path.basename(os.path.dirname(r["report_file"]))}/{os.path.basename(r["report_file"])}">Vis</a>'

        html += f"""
      <tr>
        <td>{i}</td>
        <td><a href="{r['url']}" target="_blank">{r['name']}</a></td>
        <td>{r.get('kommune', '')}</td>
        <td><span class="score-badge {score_class}">{score}%</span></td>
        <td>{mod_cell('penhet')}</td>
        <td>{mod_cell('cookie')}</td>
        <td>{mod_cell('csrd')}</td>
        <td>{mod_cell('eaa')}</td>
        <td>{report_link}</td>
      </tr>
"""

    html += f"""
    </tbody>
  </table>

  <div class="footer">
    <p>Generert av Batch Compliance Scanner &mdash; {timestamp}</p>
  </div>
</div>
</body>
</html>"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)


def generate_master_html(county_summaries, output_file):
    """Generate master summary linking all county compliance reports."""
    total_sites = sum(s['total'] for s in county_summaries.values())
    avg_score = 0
    scored = sum(s['successful'] for s in county_summaries.values())
    if scored:
        avg_score = round(sum(s['avg_score'] * s['successful'] for s in county_summaries.values()) / scored)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    score_color = "#4caf50" if avg_score >= 60 else ("#ff9800" if avg_score >= 35 else "#f44336")

    html = f"""<!DOCTYPE html>
<html lang="no">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Norge Compliance Audit</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; }}
  .container {{ max-width: 900px; margin: 0 auto; padding: 20px; }}
  h1 {{ font-size: 1.6rem; color: #1a237e; margin-bottom: 4px; }}
  .subtitle {{ color: #666; font-size: 0.9rem; margin-bottom: 20px; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .stat {{ background: white; border-radius: 10px; padding: 16px; text-align: center; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }}
  .stat .value {{ font-size: 2rem; font-weight: 700; }}
  .stat .label {{ font-size: 0.8rem; color: #888; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }}
  th {{ background: #1a237e; color: white; padding: 10px 14px; text-align: left; font-size: 0.85rem; }}
  td {{ padding: 10px 14px; border-bottom: 1px solid #f0f0f0; font-size: 0.9rem; }}
  tr:hover {{ background: #f8f9ff; }}
  .score-badge {{ display: inline-block; padding: 3px 10px; border-radius: 10px; font-weight: 600; font-size: 0.85rem; }}
  .score-badge.good {{ background: #e8f5e9; color: #2e7d32; }}
  .score-badge.warn {{ background: #fff3e0; color: #e65100; }}
  .score-badge.bad {{ background: #ffebee; color: #c62828; }}
  a {{ color: #1a237e; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .footer {{ text-align: center; color: #999; font-size: 0.8rem; margin-top: 24px; padding: 16px; }}
</style>
</head>
<body>
<div class="container">
  <h1>Norge: Compliance Audit</h1>
  <p class="subtitle">Åpenhetsloven, Cookies/Ekomlov, CSRD, EAA &mdash; {timestamp}</p>

  <div class="stats">
    <div class="stat">
      <div class="value" style="color:{score_color}">{avg_score}%</div>
      <div class="label">Gjennomsnittlig score</div>
    </div>
    <div class="stat">
      <div class="value">{len(county_summaries)}</div>
      <div class="label">Fylker skannet</div>
    </div>
    <div class="stat">
      <div class="value">{total_sites}</div>
      <div class="label">Virksomheter</div>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Fylke</th>
        <th>Virksomheter</th>
        <th>Gj.snitt score</th>
        <th>Score &ge; 60%</th>
        <th>Score &lt; 30%</th>
        <th>Rapport</th>
      </tr>
    </thead>
    <tbody>
"""

    for county in sorted(county_summaries.keys()):
        s = county_summaries[county]
        score = s['avg_score']
        score_class = "good" if score >= 60 else ("warn" if score >= 35 else "bad")
        summary_file = f"{sanitize_filename(county)}_compliance.html"

        html += f"""
      <tr>
        <td><strong>{county}</strong></td>
        <td>{s['total']}</td>
        <td><span class="score-badge {score_class}">{score}%</span></td>
        <td>{s['high_score']}</td>
        <td>{s['low_score']}</td>
        <td><a href="{summary_file}">Se rapport</a></td>
      </tr>
"""

    html += f"""
    </tbody>
  </table>

  <div class="footer">
    <p>Generert av Batch Compliance Scanner &mdash; {timestamp}</p>
  </div>
</div>
</body>
</html>"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)


def main():
    parser = argparse.ArgumentParser(description='Batch compliance scanner for Norwegian county organizations')
    parser.add_argument('--county', type=str, help='Scan only a specific county')
    parser.add_argument('--no-browser', action='store_true', help='Disable browser mode')
    parser.add_argument('--wait-for', type=str, default='load', help='Browser wait strategy')
    parser.add_argument('--reports-dir', type=str, default=REPORTS_DIR, help='Output directory')
    parser.add_argument('--resume', action='store_true', help='Resume interrupted scan')
    args = parser.parse_args()

    start_time = time.time()
    print("=" * 60)
    print("  NORWAY BATCH COMPLIANCE SCANNER")
    print("  Åpenhetsloven | Cookies/Ekomlov | CSRD | EAA")
    print("=" * 60)

    county_csvs = find_county_csvs(VIRKSOMHETER_DIR, args.county)
    if not county_csvs:
        print(f"ERROR: No county CSV files found in {VIRKSOMHETER_DIR}")
        sys.exit(1)

    print(f"Found {len(county_csvs)} county CSV files:")
    for f in county_csvs:
        print(f"  - {os.path.basename(f)}")

    os.makedirs(args.reports_dir, exist_ok=True)

    # Load resume data
    resume_data = None
    progress_file = os.path.join(args.reports_dir, '_compliance_progress.json')
    if args.resume and os.path.exists(progress_file):
        with open(progress_file, 'r', encoding='utf-8') as f:
            resume_data = json.load(f)
        print(f"\nResuming from: {progress_file}")

    use_browser = not args.no_browser
    print(f"\nBrowser mode: {'ON' if use_browser else 'OFF'}")

    checker = ComplianceChecker(use_browser=use_browser, wait_for=args.wait_for)

    all_results = dict(resume_data) if resume_data else {}
    county_summaries = {}

    # Pre-populate from resumed data
    for cname, cresults in all_results.items():
        successful = [r for r in cresults if r.get('status') == 'success']
        avg = round(sum(r.get('score_pct', 0) for r in successful) / len(successful)) if successful else 0
        county_summaries[cname] = {
            'total': len(cresults),
            'successful': len(successful),
            'avg_score': avg,
            'high_score': sum(1 for r in successful if r.get('score_pct', 0) >= 60),
            'low_score': sum(1 for r in successful if r.get('score_pct', 0) < 30),
        }

    try:
        for county_csv in county_csvs:
            results, county_name = scan_county(county_csv, checker, args.reports_dir, resume_data)

            all_results[county_name] = results

            # Generate county HTML
            summary_file = os.path.join(args.reports_dir, f"{sanitize_filename(county_name)}_compliance.html")
            generate_county_compliance_html(county_name, results, summary_file)
            print(f"\n  County compliance report: {summary_file}")

            # Stats
            successful = [r for r in results if r.get('status') == 'success']
            avg = round(sum(r.get('score_pct', 0) for r in successful) / len(successful)) if successful else 0
            county_summaries[county_name] = {
                'total': len(results),
                'successful': len(successful),
                'avg_score': avg,
                'high_score': sum(1 for r in successful if r.get('score_pct', 0) >= 60),
                'low_score': sum(1 for r in successful if r.get('score_pct', 0) < 30),
            }

            # Save progress
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, indent=2, ensure_ascii=False)

        # Master summary
        master_file = os.path.join(args.reports_dir, "norge_compliance.html")
        generate_master_html(county_summaries, master_file)

    finally:
        checker.cleanup()

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"  COMPLIANCE SCAN COMPLETE")
    print(f"{'='*60}")
    print(f"  Counties scanned:   {len(county_summaries)}")
    print(f"  Sites scanned:      {sum(s['total'] for s in county_summaries.values())}")
    print(f"  Avg score:          {round(sum(s['avg_score']*s['successful'] for s in county_summaries.values()) / max(1, sum(s['successful'] for s in county_summaries.values())))}%")
    print(f"  Time elapsed:       {elapsed/60:.1f} minutes")
    print(f"\n  Master report:      {os.path.join(args.reports_dir, 'norge_compliance.html')}")
    print(f"  Progress file:      {progress_file}")


if __name__ == "__main__":
    main()
