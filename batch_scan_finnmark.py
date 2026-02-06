#!/usr/bin/env python3
"""
Batch WCAG Scanner for Finnmark Companies
Scans all companies from FinnmarkPublic.csv and stores detailed reports.
"""

import csv
import os
import re
import json
from datetime import datetime
from urllib.parse import urlparse
from checker import WCAGChecker, SiteResult

# Configuration
CSV_FILE = "FinnmarkPublic.csv"
DETAILS_FOLDER = "details"
MAX_PAGES_PER_SITE = 20  # Limit per site to avoid very long scans
USE_BROWSER = True  # Use Playwright for JS rendering
WAIT_FOR = "load"

def sanitize_filename(name):
    """Convert company name to safe filename."""
    # Remove/replace invalid characters
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', '_', name)
    name = name.strip('_')[:50]  # Limit length
    return name.lower()

def extract_urls_from_csv(csv_file):
    """Extract unique company URLs from CSV."""
    companies = []
    seen_urls = set()

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Try different possible column names for URL
            url = None
            name = None

            # Check for URL in various columns
            for col in ['Offisiell nettside', 'nettside', 'url', 'URL']:
                if col in row and row[col] and row[col].startswith('http'):
                    url = row[col].strip()
                    break

            # Also check if URL appears in other columns (some rows have URL in wrong column)
            if not url:
                for key, value in row.items():
                    if value and value.startswith('http'):
                        url = value.strip()
                        break

            # Get company name
            for col in ['Virksomhet', 'navn', 'name', 'Organisasjon']:
                if col in row and row[col]:
                    name = row[col].strip()
                    break

            if url and url not in seen_urls:
                # Clean URL
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url

                seen_urls.add(url)
                companies.append({
                    'name': name or urlparse(url).netloc,
                    'url': url,
                    'kommune': row.get('Kommunenavn', ''),
                    'org_nr': row.get('Org nummer', '')
                })

    return companies

def scan_company(company, checker):
    """Scan a single company and return results."""
    url = company['url']
    name = company['name']

    print(f"\n{'='*60}")
    print(f"Scanning: {name}")
    print(f"URL: {url}")
    print(f"{'='*60}")

    try:
        result = checker.crawl_site(url, max_pages=MAX_PAGES_PER_SITE)
        return result
    except Exception as e:
        print(f"Error scanning {name}: {e}")
        return None

def generate_summary_html(results, output_file):
    """Generate summary HTML with links to detailed reports."""

    html = """<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Finnmark WCAG Skanningsresultater</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               line-height: 1.6; max-width: 1400px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        h1, h2 { color: #003366; }
        .header { background: #003366; color: white; padding: 30px; border-radius: 8px; margin-bottom: 20px; }
        .header h1 { margin: 0; color: white; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 20px 0; }
        .stat { background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stat-value { font-size: 2em; font-weight: bold; }
        .stat-label { color: #666; }
        .stat.critical { background: #fee; color: #c00; }
        .stat.serious { background: #fff3e0; color: #e65100; }
        .stat.success { background: #e8f5e9; color: #2e7d32; }

        table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #003366; color: white; }
        tr:hover { background: #f8f9fa; }
        .badge { padding: 4px 8px; border-radius: 4px; font-size: 0.85em; font-weight: 500; }
        .badge.critical { background: #c00; color: white; }
        .badge.serious { background: #e65100; color: white; }
        .badge.moderate { background: #f9a825; color: #333; }
        .badge.good { background: #2e7d32; color: white; }
        .badge.error { background: #666; color: white; }
        a { color: #003366; }
        .report-link { display: inline-block; padding: 6px 12px; background: #003366; color: white; text-decoration: none; border-radius: 4px; font-size: 0.9em; }
        .report-link:hover { background: #004488; }
        .footer { text-align: center; padding: 20px; color: #666; margin-top: 30px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Finnmark WCAG 2.1 Skanningsresultater</h1>
        <p>Automatisk tilgjengelighetssjekk av offentlige virksomheter i Finnmark</p>
        <p><strong>Skannet:</strong> """ + datetime.now().strftime('%Y-%m-%d %H:%M') + """</p>
    </div>
"""

    # Calculate totals
    total_sites = len(results)
    total_pages = sum(r.get('pages', 0) for r in results)
    total_issues = sum(r.get('issues', 0) for r in results)
    total_critical = sum(r.get('critical', 0) for r in results)
    total_serious = sum(r.get('serious', 0) for r in results)
    successful_scans = sum(1 for r in results if r.get('status') == 'success')

    html += f"""
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

    # Sort by critical issues (descending)
    sorted_results = sorted(results, key=lambda x: x.get('critical', 0), reverse=True)

    for r in sorted_results:
        status_badge = 'good' if r.get('status') == 'success' else 'error'
        status_text = 'OK' if r.get('status') == 'success' else 'Feil'

        critical_badge = 'critical' if r.get('critical', 0) > 50 else ('serious' if r.get('critical', 0) > 10 else 'moderate')

        report_link = f'<a href="{r.get("report_file", "#")}" class="report-link">Se rapport</a>' if r.get('report_file') else '-'

        html += f"""
            <tr>
                <td><a href="{r.get('url', '#')}" target="_blank">{r.get('name', 'Ukjent')}</a></td>
                <td>{r.get('kommune', '-')}</td>
                <td>{r.get('pages', 0)}</td>
                <td><span class="badge {critical_badge}">{r.get('critical', 0)}</span></td>
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

    print(f"\nSummary saved to: {output_file}")

def main():
    """Main batch scanning function."""
    print("="*60)
    print("FINNMARK BATCH WCAG SCANNER")
    print("="*60)

    # Ensure details folder exists
    os.makedirs(DETAILS_FOLDER, exist_ok=True)

    # Extract companies from CSV
    print(f"\nReading companies from {CSV_FILE}...")
    companies = extract_urls_from_csv(CSV_FILE)
    print(f"Found {len(companies)} unique company URLs")

    # Create checker
    checker = WCAGChecker(
        use_browser=USE_BROWSER,
        wait_for=WAIT_FOR,
        dedupe_articles=True
    )

    results = []

    for i, company in enumerate(companies, 1):
        print(f"\n[{i}/{len(companies)}] ", end="")

        result_data = {
            'name': company['name'],
            'url': company['url'],
            'kommune': company['kommune'],
            'org_nr': company['org_nr'],
            'status': 'error',
            'pages': 0,
            'issues': 0,
            'critical': 0,
            'serious': 0,
            'moderate': 0,
            'minor': 0,
            'report_file': None
        }

        try:
            result = scan_company(company, checker)

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
                report_path = os.path.join(DETAILS_FOLDER, filename)

                report_html = checker.generate_report(result, format='html')
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(report_html)

                result_data['report_file'] = report_path
                print(f"  -> Saved: {report_path}")
                print(f"  -> Issues: {summary['issues']} (Critical: {summary['critical']}, Serious: {summary['serious']})")

        except Exception as e:
            print(f"  -> Error: {e}")
            result_data['error'] = str(e)

        results.append(result_data)

        # Save intermediate results
        with open('finnmark_scan_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    # Generate summary HTML
    generate_summary_html(results, 'finnmark_summary.html')

    # Final summary
    print("\n" + "="*60)
    print("SCAN COMPLETE")
    print("="*60)
    print(f"Sites scanned: {len(results)}")
    print(f"Successful: {sum(1 for r in results if r['status'] == 'success')}")
    print(f"Failed: {sum(1 for r in results if r['status'] == 'error')}")
    print(f"Total issues found: {sum(r['issues'] for r in results)}")
    print(f"\nReports saved to: {DETAILS_FOLDER}/")
    print(f"Summary: finnmark_summary.html")

if __name__ == "__main__":
    main()
