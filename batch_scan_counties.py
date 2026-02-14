#!/usr/bin/env python3
"""
Batch WCAG Scanner for All Norwegian Counties.
Scans all organizations from per-county CSVs and generates summary reports.

Usage:
    python batch_scan_counties.py                        # Scan all counties
    python batch_scan_counties.py --county Finnmark      # Scan specific county
    python batch_scan_counties.py --county Oslo --max-pages 10  # Limit pages
    python batch_scan_counties.py --no-browser           # Skip JS rendering
    python batch_scan_counties.py --resume               # Resume interrupted scan
"""

import argparse
import csv
import glob
import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urlparse

from checker import WCAGChecker

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIRKSOMHETER_DIR = os.path.join(SCRIPT_DIR, "Virksomheter")
REPORTS_DIR = os.path.join(SCRIPT_DIR, "reports", "counties")
MAX_PAGES_PER_SITE = 20
USE_BROWSER = True
WAIT_FOR = "load"


def sanitize_filename(name):
    """Convert name to safe filename."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', '_', name)
    name = name.strip('_')[:50]
    return name.lower()


def find_county_csvs(virksomheter_dir, county_filter=None):
    """Find all *Public.csv files in the Virksomheter directory."""
    pattern = os.path.join(virksomheter_dir, "*Public.csv")
    files = glob.glob(pattern)

    # Exclude the old nationwide file
    files = [f for f in files if 'komplett' not in f.lower()]

    if county_filter:
        filter_lower = county_filter.lower()
        files = [f for f in files if filter_lower in os.path.basename(f).lower()]

    # Sort alphabetically but put Oslo last (largest county, ~1100 sites)
    def _sort_key(f):
        name = os.path.basename(f).lower()
        if name.startswith('oslo'):
            return (1, name)
        return (0, name)

    return sorted(files, key=_sort_key)


def extract_urls_from_csv(csv_file):
    """Extract unique company URLs from a county CSV."""
    companies = []
    seen_urls = set()

    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get('Offisiell nettside', '').strip()
            name = row.get('Virksomhet', '').strip()

            if not url or not url.startswith('http'):
                continue

            # Normalize URL for dedup
            url_key = url.rstrip('/').lower()
            if url_key in seen_urls:
                continue

            seen_urls.add(url_key)
            companies.append({
                'name': name or urlparse(url).netloc,
                'url': url,
                'kommune': row.get('Kommunenavn', ''),
                'org_nr': row.get('Org nummer', ''),
                'epost': row.get('Epost', ''),
                'telefon': row.get('Telefon', ''),
            })

    return companies


def scan_company(company, checker, max_pages):
    """Scan a single company and return results."""
    url = company['url']
    name = company['name']

    print(f"\n{'='*60}")
    print(f"Scanning: {name}")
    print(f"URL: {url}")
    print(f"{'='*60}")

    try:
        result = checker.crawl_site(url, max_pages=max_pages)
        return result
    except Exception as e:
        print(f"Error scanning {name}: {e}")
        return None


def generate_county_summary_html(county_name, results, output_file, details_dir):
    """Generate summary HTML for a single county."""
    total_sites = len(results)
    total_pages = sum(r.get('pages', 0) for r in results)
    total_issues = sum(r.get('issues', 0) for r in results)
    total_critical = sum(r.get('critical', 0) for r in results)
    total_serious = sum(r.get('serious', 0) for r in results)
    successful_scans = sum(1 for r in results if r.get('status') == 'success')
    failed_scans = total_sites - successful_scans

    html = f"""<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{county_name} WCAG Skanningsresultater</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               line-height: 1.6; max-width: 1400px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        h1, h2 {{ color: #003366; }}
        .header {{ background: #003366; color: white; padding: 30px; border-radius: 8px; margin-bottom: 20px; }}
        .header h1 {{ margin: 0; color: white; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 20px 0; }}
        .stat {{ background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-value {{ font-size: 2em; font-weight: bold; }}
        .stat-label {{ color: #666; }}
        .stat.critical {{ background: #fee; color: #c00; }}
        .stat.serious {{ background: #fff3e0; color: #e65100; }}
        .stat.success {{ background: #e8f5e9; color: #2e7d32; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #003366; color: white; cursor: pointer; }}
        th:hover {{ background: #004488; }}
        tr:hover {{ background: #f8f9fa; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.85em; font-weight: 500; }}
        .badge.critical {{ background: #c00; color: white; }}
        .badge.serious {{ background: #e65100; color: white; }}
        .badge.moderate {{ background: #f9a825; color: #333; }}
        .badge.good {{ background: #2e7d32; color: white; }}
        .badge.error {{ background: #666; color: white; }}
        a {{ color: #003366; }}
        .report-link {{ display: inline-block; padding: 6px 12px; background: #003366; color: white; text-decoration: none; border-radius: 4px; font-size: 0.9em; }}
        .report-link:hover {{ background: #004488; }}
        .footer {{ text-align: center; padding: 20px; color: #666; margin-top: 30px; }}
        .contact {{ font-size: 0.85em; color: #555; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{county_name} WCAG 2.1 Skanningsresultater</h1>
        <p>Automatisk tilgjengelighetssjekk av offentlige virksomheter i {county_name}</p>
        <p><strong>Skannet:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    </div>

    <div class="stats">
        <div class="stat">
            <div class="stat-value">{total_sites}</div>
            <div class="stat-label">Nettsteder skannet</div>
        </div>
        <div class="stat success">
            <div class="stat-value">{successful_scans}</div>
            <div class="stat-label">Vellykkede skanninger</div>
        </div>
        <div class="stat">
            <div class="stat-value">{total_pages}</div>
            <div class="stat-label">Sider sjekket</div>
        </div>
        <div class="stat critical">
            <div class="stat-value">{total_critical}</div>
            <div class="stat-label">Kritiske feil</div>
        </div>
        <div class="stat serious">
            <div class="stat-value">{total_serious}</div>
            <div class="stat-label">Alvorlige feil</div>
        </div>
        <div class="stat">
            <div class="stat-value">{total_issues}</div>
            <div class="stat-label">Totale avvik</div>
        </div>
    </div>

    <h2>Resultater per virksomhet</h2>
    <table>
        <thead>
            <tr>
                <th>Virksomhet</th>
                <th>Kommune</th>
                <th>Kontakt</th>
                <th>Sider</th>
                <th>Kritisk</th>
                <th>Alvorlig</th>
                <th>Moderat</th>
                <th>Totalt</th>
                <th>Status</th>
                <th>Rapport</th>
            </tr>
        </thead>
        <tbody>
"""

    sorted_results = sorted(results, key=lambda x: x.get('critical', 0), reverse=True)

    for r in sorted_results:
        status_badge = 'good' if r.get('status') == 'success' else 'error'
        status_text = 'OK' if r.get('status') == 'success' else 'Feil'

        crit = r.get('critical', 0)
        critical_badge = 'critical' if crit > 50 else ('serious' if crit > 10 else ('moderate' if crit > 0 else 'good'))

        report_file = r.get('report_file', '')
        if report_file:
            rel_path = os.path.relpath(report_file, os.path.dirname(output_file))
            report_link = f'<a href="{rel_path}" class="report-link">Se rapport</a>'
        else:
            report_link = '-'

        # Contact info
        contact_parts = []
        if r.get('epost'):
            contact_parts.append(f'<a href="mailto:{r["epost"]}">{r["epost"]}</a>')
        if r.get('telefon'):
            contact_parts.append(r['telefon'])
        contact_html = '<br>'.join(contact_parts) if contact_parts else '-'

        name_escaped = (r.get('name') or 'Ukjent').replace('&', '&amp;').replace('<', '&lt;')
        url_escaped = (r.get('url') or '#').replace('&', '&amp;')

        html += f"""
            <tr>
                <td><a href="{url_escaped}" target="_blank">{name_escaped}</a></td>
                <td>{r.get('kommune', '-')}</td>
                <td class="contact">{contact_html}</td>
                <td>{r.get('pages', 0)}</td>
                <td><span class="badge {critical_badge}">{crit}</span></td>
                <td>{r.get('serious', 0)}</td>
                <td>{r.get('moderate', 0)}</td>
                <td>{r.get('issues', 0)}</td>
                <td><span class="badge {status_badge}">{status_text}</span></td>
                <td>{report_link}</td>
            </tr>
"""

    html += """
        </tbody>
    </table>

    <div class="footer">
        <p>Generert av WCAG Checker - Basert på testregler fra UU-tilsynet</p>
    </div>
</body>
</html>
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)


def generate_nationwide_summary_html(county_summaries, output_file):
    """Generate a master summary HTML linking to all county reports."""
    total_sites = sum(s['total_sites'] for s in county_summaries.values())
    total_issues = sum(s['total_issues'] for s in county_summaries.values())
    total_critical = sum(s['total_critical'] for s in county_summaries.values())
    total_serious = sum(s['total_serious'] for s in county_summaries.values())

    html = f"""<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Norge WCAG Skanningsresultater - Alle fylker</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               line-height: 1.6; max-width: 1400px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        h1, h2 {{ color: #003366; }}
        .header {{ background: #003366; color: white; padding: 30px; border-radius: 8px; margin-bottom: 20px; }}
        .header h1 {{ margin: 0; color: white; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin: 20px 0; }}
        .stat {{ background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-value {{ font-size: 2em; font-weight: bold; }}
        .stat-label {{ color: #666; }}
        .stat.critical {{ background: #fee; color: #c00; }}
        .stat.serious {{ background: #fff3e0; color: #e65100; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #003366; color: white; }}
        tr:hover {{ background: #f8f9fa; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.85em; font-weight: 500; }}
        .badge.critical {{ background: #c00; color: white; }}
        .badge.serious {{ background: #e65100; color: white; }}
        .badge.moderate {{ background: #f9a825; color: #333; }}
        .badge.good {{ background: #2e7d32; color: white; }}
        a {{ color: #003366; }}
        .report-link {{ display: inline-block; padding: 6px 12px; background: #003366; color: white; text-decoration: none; border-radius: 4px; font-size: 0.9em; }}
        .report-link:hover {{ background: #004488; }}
        .footer {{ text-align: center; padding: 20px; color: #666; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Norge WCAG 2.1 Skanningsresultater</h1>
        <p>Tilgjengelighetssjekk av offentlige virksomheter i alle fylker</p>
        <p><strong>Generert:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    </div>

    <div class="stats">
        <div class="stat">
            <div class="stat-value">{len(county_summaries)}</div>
            <div class="stat-label">Fylker skannet</div>
        </div>
        <div class="stat">
            <div class="stat-value">{total_sites}</div>
            <div class="stat-label">Nettsteder totalt</div>
        </div>
        <div class="stat critical">
            <div class="stat-value">{total_critical}</div>
            <div class="stat-label">Kritiske feil totalt</div>
        </div>
        <div class="stat serious">
            <div class="stat-value">{total_serious}</div>
            <div class="stat-label">Alvorlige feil totalt</div>
        </div>
        <div class="stat">
            <div class="stat-value">{total_issues}</div>
            <div class="stat-label">Totale avvik</div>
        </div>
    </div>

    <h2>Resultater per fylke</h2>
    <table>
        <thead>
            <tr>
                <th>Fylke</th>
                <th>Nettsteder</th>
                <th>Vellykkede</th>
                <th>Sider sjekket</th>
                <th>Kritiske feil</th>
                <th>Alvorlige feil</th>
                <th>Totale avvik</th>
                <th>Rapport</th>
            </tr>
        </thead>
        <tbody>
"""

    for county_name in sorted(county_summaries.keys()):
        s = county_summaries[county_name]
        crit = s['total_critical']
        critical_badge = 'critical' if crit > 500 else ('serious' if crit > 100 else 'moderate')

        report_file = s.get('report_file', '')
        if report_file:
            rel_path = os.path.relpath(report_file, os.path.dirname(output_file))
            report_link = f'<a href="{rel_path}" class="report-link">Se detaljer</a>'
        else:
            report_link = '-'

        html += f"""
            <tr>
                <td><strong>{county_name}</strong></td>
                <td>{s['total_sites']}</td>
                <td>{s['successful']}</td>
                <td>{s['total_pages']}</td>
                <td><span class="badge {critical_badge}">{crit}</span></td>
                <td>{s['total_serious']}</td>
                <td>{s['total_issues']}</td>
                <td>{report_link}</td>
            </tr>
"""

    html += """
        </tbody>
    </table>

    <div class="footer">
        <p>Generert av WCAG Checker - Basert på testregler fra UU-tilsynet</p>
    </div>
</body>
</html>
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)


def scan_county(county_csv, checker, reports_dir, max_pages, resume_data=None):
    """Scan all organizations in a county CSV. Returns (results, county_name)."""
    county_name = os.path.basename(county_csv).replace('Public.csv', '')
    county_dir = os.path.join(reports_dir, sanitize_filename(county_name))
    os.makedirs(county_dir, exist_ok=True)

    companies = extract_urls_from_csv(county_csv)
    print(f"\n{'#'*60}")
    print(f"# {county_name}: {len(companies)} organizations with URLs")
    print(f"{'#'*60}")

    # Load resume data if available
    completed_urls = set()
    results = []
    if resume_data and county_name in resume_data:
        results = resume_data[county_name]
        completed_urls = {r['url'] for r in results}
        print(f"  Resuming: {len(completed_urls)} already scanned")

    for i, company in enumerate(companies, 1):
        if company['url'] in completed_urls:
            continue

        print(f"\n  [{i}/{len(companies)}] ", end="")

        result_data = {
            'name': company['name'],
            'url': company['url'],
            'kommune': company['kommune'],
            'org_nr': company['org_nr'],
            'epost': company.get('epost', ''),
            'telefon': company.get('telefon', ''),
            'status': 'error',
            'pages': 0,
            'issues': 0,
            'critical': 0,
            'serious': 0,
            'moderate': 0,
            'minor': 0,
            'report_file': None,
        }

        try:
            result = scan_company(company, checker, max_pages)

            if result:
                summary = result.summary
                result_data['status'] = 'success'
                result_data['pages'] = summary['pages_checked']
                result_data['issues'] = summary['issues']
                result_data['critical'] = summary['critical']
                result_data['serious'] = summary['serious']
                result_data['moderate'] = summary['moderate']
                result_data['minor'] = summary['minor']

                # Save detailed report
                filename = sanitize_filename(company['name']) + '.html'
                report_path = os.path.join(county_dir, filename)

                report_html = checker.generate_report(result, format='html')
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(report_html)

                result_data['report_file'] = report_path
                print(f"  -> Issues: {summary['issues']} (Critical: {summary['critical']}, Serious: {summary['serious']})")

        except Exception as e:
            print(f"  -> Error: {e}")
            result_data['error'] = str(e)

        results.append(result_data)

    return results, county_name, county_dir


def main():
    parser = argparse.ArgumentParser(
        description='Batch WCAG scanner for all Norwegian county organizations'
    )
    parser.add_argument('--county', type=str, help='Scan only a specific county')
    parser.add_argument('--max-pages', type=int, default=MAX_PAGES_PER_SITE,
                        help=f'Max pages per site (default: {MAX_PAGES_PER_SITE})')
    parser.add_argument('--no-browser', action='store_true',
                        help='Disable browser mode (use static HTML only)')
    parser.add_argument('--wait-for', type=str, default=WAIT_FOR,
                        help=f'Browser wait strategy (default: {WAIT_FOR})')
    parser.add_argument('--reports-dir', type=str, default=REPORTS_DIR,
                        help='Output directory for reports')
    parser.add_argument('--resume', action='store_true',
                        help='Resume interrupted scan from saved progress')
    args = parser.parse_args()

    start_time = time.time()
    print("=" * 60)
    print("  NORWAY BATCH WCAG SCANNER")
    print("=" * 60)

    # Find county CSVs
    county_csvs = find_county_csvs(VIRKSOMHETER_DIR, args.county)
    if not county_csvs:
        print(f"ERROR: No county CSV files found in {VIRKSOMHETER_DIR}")
        if args.county:
            print(f"  (filtered by: {args.county})")
        sys.exit(1)

    print(f"Found {len(county_csvs)} county CSV files:")
    for f in county_csvs:
        print(f"  - {os.path.basename(f)}")

    # Create reports directory
    os.makedirs(args.reports_dir, exist_ok=True)

    # Load resume data if requested
    resume_data = None
    progress_file = os.path.join(args.reports_dir, '_scan_progress.json')
    if args.resume and os.path.exists(progress_file):
        with open(progress_file, 'r', encoding='utf-8') as f:
            resume_data = json.load(f)
        print(f"\nResuming from saved progress: {progress_file}")

    # Create checker
    use_browser = not args.no_browser
    print(f"\nBrowser mode: {'ON' if use_browser else 'OFF'}")
    print(f"Max pages per site: {args.max_pages}")
    print(f"Reports dir: {args.reports_dir}")

    checker = WCAGChecker(
        use_browser=use_browser,
        wait_for=args.wait_for,
        dedupe_articles=True,
    )

    # Scan each county (preserve previous results when resuming)
    all_county_results = dict(resume_data) if resume_data else {}
    county_summaries = {}

    # Pre-populate county_summaries from resumed data
    for cname, cresults in all_county_results.items():
        summary_file = os.path.join(args.reports_dir, f"{sanitize_filename(cname)}_summary.html")
        county_summaries[cname] = {
            'total_sites': len(cresults),
            'successful': sum(1 for r in cresults if r.get('status') == 'success'),
            'total_pages': sum(r.get('pages', 0) for r in cresults),
            'total_issues': sum(r.get('issues', 0) for r in cresults),
            'total_critical': sum(r.get('critical', 0) for r in cresults),
            'total_serious': sum(r.get('serious', 0) for r in cresults),
            'report_file': summary_file,
        }

    for county_csv in county_csvs:
        results, county_name, county_dir = scan_county(
            county_csv, checker, args.reports_dir, args.max_pages, resume_data
        )

        all_county_results[county_name] = results

        # Generate county summary HTML
        summary_file = os.path.join(args.reports_dir, f"{sanitize_filename(county_name)}_summary.html")
        generate_county_summary_html(county_name, results, summary_file, county_dir)
        print(f"\n  County summary: {summary_file}")

        # Calculate county stats
        county_summaries[county_name] = {
            'total_sites': len(results),
            'successful': sum(1 for r in results if r.get('status') == 'success'),
            'total_pages': sum(r.get('pages', 0) for r in results),
            'total_issues': sum(r.get('issues', 0) for r in results),
            'total_critical': sum(r.get('critical', 0) for r in results),
            'total_serious': sum(r.get('serious', 0) for r in results),
            'report_file': summary_file,
        }

        # Save progress after each county
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(all_county_results, f, indent=2, ensure_ascii=False)

    # Generate nationwide master summary
    master_file = os.path.join(args.reports_dir, "norge_summary.html")
    generate_nationwide_summary_html(county_summaries, master_file)

    # Save final results JSON
    results_file = os.path.join(args.reports_dir, "norge_scan_results.json")
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            'generated': datetime.now().isoformat(),
            'county_summaries': county_summaries,
            'detailed_results': all_county_results,
        }, f, indent=2, ensure_ascii=False)

    # Print final summary
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("  SCAN COMPLETE")
    print("=" * 60)

    total_sites = sum(s['total_sites'] for s in county_summaries.values())
    total_success = sum(s['successful'] for s in county_summaries.values())
    total_issues = sum(s['total_issues'] for s in county_summaries.values())
    total_critical = sum(s['total_critical'] for s in county_summaries.values())

    print(f"  Counties scanned:   {len(county_summaries)}")
    print(f"  Sites scanned:      {total_sites}")
    print(f"  Successful:         {total_success}")
    print(f"  Total issues:       {total_issues}")
    print(f"  Critical issues:    {total_critical}")
    print(f"  Time elapsed:       {elapsed/60:.1f} minutes")
    print(f"\n  Master summary:     {master_file}")
    print(f"  Detailed results:   {results_file}")
    print(f"  Reports directory:  {args.reports_dir}")


if __name__ == '__main__':
    main()
