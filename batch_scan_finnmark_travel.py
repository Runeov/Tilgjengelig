#!/usr/bin/env python3
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
Batch Travel Compliance Scanner — Finnmark
==========================================
Scans Norwegian travel businesses in Finnmark against a custom rule set covering:
  - Price / VAT transparency       (Markedsføringsloven §7)
  - Contact information            (ehandelsloven §8)
  - Cancellation policy & GDPR     (Angrerettloven, GDPR)
  - Regulatory identity            (Enhetsregisterloven, Pakkereiseloven)

Data source: FinnmarkTravel.csv
Output:      reports/travel/finnmark/  (individual HTML reports)
             travel_finnmark_results.json
             travel_finnmark_summary.html

Usage:
    python batch_scan_finnmark_travel.py
    python batch_scan_finnmark_travel.py --category "Opplevelse og aktivitet"
    python batch_scan_finnmark_travel.py --max-pages 5
    python batch_scan_finnmark_travel.py --no-browser
"""

import csv
import os
import re
import json
import argparse
import time
from datetime import datetime
from urllib.parse import urlparse, urljoin
from collections import deque

import requests as http_requests
from bs4 import BeautifulSoup

# ── Travel-specific checkers ──────────────────────────────────────────────────
from checkers.pricing import check_pricing
from checkers.contact_info import check_contact_info
from checkers.cancellation_policy import check_cancellation_policy
from checkers.regulatory import check_regulatory

# ── Configuration ────────────────────────────────────────────────────────────
CSV_FILE = "FinnmarkTravel.csv"
OUTPUT_DIR = os.path.join("reports", "travel", "finnmark")
RESULTS_JSON = "travel_finnmark_results.json"
SUMMARY_HTML = "travel_finnmark_summary.html"
MAX_PAGES = 10
REQUEST_TIMEOUT = 20
CRAWL_DELAY = 0.5

# Skip these extensions when crawling
SKIP_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.rar', '.exe', '.dmg',
    '.mp3', '.mp4', '.avi', '.mov', '.wmv',
    '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico',
}


# ── Travel checker registry (mirrors WCAGChecker.checkers pattern) ────────────
TRAVEL_CHECKERS = [
    ("Pricing",              check_pricing),
    ("Contact Info",         check_contact_info),
    ("Cancellation & GDPR",  check_cancellation_policy),
    ("Regulatory",           check_regulatory),
]


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*æøåÆØÅ]', lambda m: {
        'æ': 'ae', 'ø': 'oe', 'å': 'aa',
        'Æ': 'Ae', 'Ø': 'Oe', 'Å': 'Aa'
    }.get(m.group(0), ''), name)
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^a-zA-Z0-9_\-]', '', name)
    return name.strip('_')[:60].lower()


def load_companies(csv_file: str, category_filter: str = None) -> list:
    """Load travel companies from CSV, optionally filtered by category."""
    companies = []
    seen_urls = set()

    with open(csv_file, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get('url', '').strip()
            if not url or not url.startswith('http'):
                continue
            if url in seen_urls:
                continue
            if category_filter and row.get('category_name', '') != category_filter:
                continue

            seen_urls.add(url)
            companies.append({
                'category_id':   row.get('category_id', ''),
                'category_name': row.get('category_name', ''),
                'company_id':    row.get('company_id', ''),
                'name':          row.get('company_name', urlparse(url).netloc),
                'url':           url,
                'org_nr':        row.get('org_nr', ''),
                'municipality':  row.get('municipality', ''),
                'region':        row.get('region', ''),
                'notes':         row.get('notes', ''),
            })

    return companies


def run_travel_checkers(soup, url: str, html: str) -> tuple:
    """Run all travel checkers and aggregate results."""
    all_issues = []
    all_passed = []
    all_warnings = []

    for name, checker_fn in TRAVEL_CHECKERS:
        try:
            issues, passed, warnings = checker_fn(soup, url, html)
            all_issues.extend(issues)
            all_passed.extend(passed)
            all_warnings.extend(warnings)
        except Exception as e:
            all_warnings.append(f"Checker '{name}' feilet: {e}")

    return all_issues, all_passed, all_warnings


def _extract_links(soup: BeautifulSoup, base_url: str) -> list:
    """Extract same-domain links from a parsed page."""
    base_parsed = urlparse(base_url)
    links = set()

    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
            continue

        full = urljoin(base_url, href)
        parsed = urlparse(full)

        # Same domain only
        if parsed.netloc != base_parsed.netloc:
            continue

        # Skip file downloads
        ext = os.path.splitext(parsed.path)[1].lower()
        if ext in SKIP_EXTENSIONS:
            continue

        # Clean URL (strip fragment)
        clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            clean += f"?{parsed.query}"
        links.add(clean)

    return list(links)


def crawl_and_check(url: str, max_pages: int, session: http_requests.Session) -> dict:
    """
    Crawl a site with plain requests (no Playwright), run travel checkers
    on each page. Returns a site result dict with pages, issues, passed, warnings.
    """
    visited = set()
    queue = deque([url])
    pages = []

    while queue and len(visited) < max_pages:
        current_url = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)

        try:
            resp = session.get(current_url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if resp.status_code != 200:
                continue
            content_type = resp.headers.get('content-type', '')
            if 'text/html' not in content_type:
                continue

            html = resp.text
            soup = BeautifulSoup(html, 'lxml')
            title = soup.title.string.strip() if soup.title and soup.title.string else current_url

            # Run all travel checkers
            issues, passed, warnings = run_travel_checkers(soup, current_url, html)

            pages.append({
                'url': current_url,
                'title': title,
                'issues': issues,
                'passed': passed,
                'warnings': warnings,
            })

            # Extract links for crawling
            if len(visited) < max_pages:
                for link in _extract_links(soup, current_url):
                    if link not in visited:
                        queue.append(link)

            if len(visited) > 1:
                time.sleep(CRAWL_DELAY)

        except Exception as e:
            pages.append({
                'url': current_url,
                'title': current_url,
                'issues': [],
                'passed': [],
                'warnings': [f"Feil ved henting: {e}"],
            })

    return {
        'base_url': url,
        'pages': pages,
    }


def _count_by_impact(pages: list) -> dict:
    """Count issues by impact across all pages."""
    counts = {'critical': 0, 'serious': 0, 'moderate': 0, 'minor': 0}
    for page in pages:
        for issue in page['issues']:
            impact = issue.impact if hasattr(issue, 'impact') else issue.get('impact', '')
            if impact in counts:
                counts[impact] += 1
    total = sum(counts.values())
    total_passed = sum(len(p['passed']) for p in pages)
    return {**counts, 'issues': total, 'passed': total_passed, 'pages_checked': len(pages)}


def scan_company(company: dict, session: http_requests.Session, max_pages: int) -> dict:
    """
    Crawl and scan a single company with travel compliance checkers.
    Uses plain HTTP requests — no Playwright needed.
    """
    url = company['url']
    print(f"{'─'*60}")
    print(f"  {company['name']}")
    print(f"  {url}")
    print(f"  Kategori: {company['category_name']} | Kommune: {company['municipality']}")
    print(f"{'─'*60}")

    result_data = {
        'name':          company['name'],
        'url':           url,
        'category':      company['category_name'],
        'org_nr':        company['org_nr'],
        'municipality':  company['municipality'],
        'region':        company['region'],
        'notes':         company['notes'],
        'status':        'error',
        'pages':         0,
        'issues':        0,
        'critical':      0,
        'serious':       0,
        'moderate':      0,
        'minor':         0,
        'report_file':   None,
        'error':         None,
        'timestamp':     datetime.now().isoformat(),
    }

    try:
        site = crawl_and_check(url, max_pages, session)
        pages = site['pages']

        if pages:
            summary = _count_by_impact(pages)
            result_data['status']   = 'success'
            result_data['pages']    = summary['pages_checked']
            result_data['issues']   = summary['issues']
            result_data['critical'] = summary['critical']
            result_data['serious']  = summary['serious']
            result_data['moderate'] = summary['moderate']
            result_data['minor']    = summary['minor']

            # Generate and save HTML report
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            filename = sanitize_filename(company['name']) + '.html'
            report_path = os.path.join(OUTPUT_DIR, filename)

            report_html = _generate_travel_report_html(company, site)
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_html)

            result_data['report_file'] = report_path
            print(f"  OK — {summary['pages_checked']} sider, {summary['issues']} avvik "
                  f"(kritisk: {summary['critical']}, alvorlig: {summary['serious']})")
            print(f"  -> {report_path}")
        else:
            result_data['error'] = "Ingen sider hentet"
            print(f"  !! Ingen sider hentet")

    except Exception as e:
        result_data['error'] = str(e)
        print(f"  !! Feil: {e}")

    return result_data


def _severity_class(count: int, thresholds=(1, 10, 25)) -> str:
    """Return CSS class based on issue count."""
    if count == 0:
        return 'good'
    if count <= thresholds[0]:
        return 'minor'
    if count <= thresholds[1]:
        return 'moderate'
    if count <= thresholds[2]:
        return 'serious'
    return 'critical'


def _generate_travel_report_html(company: dict, site: dict) -> str:
    """Generate a detailed HTML report for a single travel company."""
    pages = site['pages']
    summary = _count_by_impact(pages)
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Group issues by rule criterion
    all_issues = [i for page in pages for i in page['issues']]
    by_criterion = {}
    for issue in all_issues:
        key = issue.criterion_id
        by_criterion.setdefault(key, {
            'name': issue.criterion_name,
            'name_en': issue.criterion_name_en,
            'issues': []
        })
        by_criterion[key]['issues'].append(issue)

    issues_rows = ""
    for criterion_id, data in sorted(by_criterion.items()):
        issues_rows += f"""
        <tr>
            <td colspan="5" class="criterion-header">
                {criterion_id} — {data['name']} / {data['name_en']}
                <span class="badge {'critical' if len(data['issues']) > 10 else 'serious'}">
                    {len(data['issues'])} avvik
                </span>
            </td>
        </tr>"""
        for iss in data['issues'][:20]:  # Cap at 20 per criterion
            impact_class = iss.impact if iss.impact in ('critical','serious','moderate','minor') else 'moderate'
            issues_rows += f"""
        <tr>
            <td><span class="badge {impact_class}">{iss.impact}</span></td>
            <td><code>{iss.rule_id}</code></td>
            <td>{iss.issue}</td>
            <td class="fix-text">{iss.fix}</td>
            <td><code class="selector">{iss.selector[:60]}</code></td>
        </tr>"""
        if len(data['issues']) > 20:
            issues_rows += f"""
        <tr><td colspan="5" class="more-note">
            … og {len(data['issues']) - 20} flere avvik i denne kategorien
        </td></tr>"""

    # Passed checks list
    all_passed = [p for page in pages for p in page['passed']]
    passed_list = "".join(f"<li>{p}</li>" for p in sorted(set(all_passed))[:40])

    # All warnings
    all_warnings = [w for page in pages for w in page['warnings']]
    warn_list = "".join(f"<li class='warn-item'>{w}</li>" for w in all_warnings[:20])

    return f"""<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reiselivssjekk – {company['name']}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                line-height: 1.6; max-width: 1300px; margin: 0 auto; padding: 20px;
                background: #f0f4f8; color: #222; }}
        .header {{ background: linear-gradient(135deg, #1a3a5c, #0e5f8a);
                   color: white; padding: 30px; border-radius: 10px; margin-bottom: 24px; }}
        .header h1 {{ margin: 0 0 6px; font-size: 1.6em; }}
        .header p {{ margin: 4px 0; opacity: 0.85; font-size: 0.95em; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
                  gap: 14px; margin-bottom: 24px; }}
        .stat {{ background: white; padding: 18px; border-radius: 8px; text-align: center;
                 box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
        .stat-val {{ font-size: 2.2em; font-weight: 700; }}
        .stat-lbl {{ color: #666; font-size: 0.85em; margin-top: 4px; }}
        .stat.critical {{ background: #fff0f0; }}  .stat.critical .stat-val {{ color: #c00; }}
        .stat.serious  {{ background: #fff8f0; }}  .stat.serious  .stat-val {{ color: #e05800; }}
        .stat.good     {{ background: #f0fff4; }}  .stat.good     .stat-val {{ color: #1a7a3c; }}
        section {{ background: white; border-radius: 8px; padding: 24px;
                   margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
        section h2 {{ color: #1a3a5c; margin-top: 0; border-bottom: 2px solid #e8eef4;
                      padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.92em; }}
        th {{ background: #1a3a5c; color: white; padding: 10px 12px; text-align: left; }}
        td {{ padding: 9px 12px; border-bottom: 1px solid #eee; vertical-align: top; }}
        .criterion-header {{ background: #f0f4f8; font-weight: 600; color: #1a3a5c;
                              padding: 10px 12px; }}
        .more-note {{ color: #888; font-style: italic; font-size: 0.88em; }}
        .fix-text {{ color: #555; font-size: 0.9em; max-width: 340px; }}
        .selector {{ font-size: 0.82em; color: #666; background: #f5f5f5;
                     padding: 2px 5px; border-radius: 3px; }}
        .badge {{ display: inline-block; padding: 3px 8px; border-radius: 4px;
                  font-size: 0.82em; font-weight: 600; white-space: nowrap; }}
        .badge.critical {{ background: #c00;    color: #fff; }}
        .badge.serious   {{ background: #e05800; color: #fff; }}
        .badge.moderate  {{ background: #f9a825; color: #333; }}
        .badge.minor     {{ background: #7cb9e8; color: #000; }}
        .badge.good      {{ background: #1a7a3c; color: #fff; }}
        .passed-list, .warn-list {{ list-style: none; padding: 0; margin: 0; }}
        .passed-list li {{ padding: 5px 0 5px 24px; border-bottom: 1px solid #f0f4f8;
                           position: relative; }}
        .passed-list li::before {{ content: '✓'; color: #1a7a3c; position: absolute; left: 4px; }}
        .warn-item {{ padding: 6px 0 6px 24px; border-bottom: 1px solid #fff8ee;
                      position: relative; color: #7a5500; }}
        .warn-item::before {{ content: '⚠'; position: absolute; left: 2px; }}
        .meta-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
                      font-size: 0.92em; }}
        .meta-item {{ background: #f8f9fa; padding: 10px 14px; border-radius: 6px; }}
        .meta-item strong {{ display: block; color: #1a3a5c; margin-bottom: 2px; }}
        .footer {{ text-align: center; color: #888; padding: 20px; font-size: 0.85em; }}
        @media (max-width: 700px) {{
            .meta-grid {{ grid-template-columns: 1fr; }}
            .stats {{ grid-template-columns: repeat(3, 1fr); }}
        }}
    </style>
</head>
<body>

<div class="header">
    <h1>Reiselivssjekk — {company['name']}</h1>
    <p><strong>Nettsted:</strong> <a href="{company['url']}" style="color:#7ec8f0">{company['url']}</a></p>
    <p><strong>Kategori:</strong> {company['category_name']} &nbsp;|&nbsp;
       <strong>Kommune:</strong> {company['municipality']} &nbsp;|&nbsp;
       <strong>Region:</strong> {company['region']}</p>
    <p><strong>Skannet:</strong> {ts} &nbsp;|&nbsp; <strong>Sider sjekket:</strong> {summary['pages_checked']}</p>
</div>

<div class="stats">
    <div class="stat">
        <div class="stat-val">{summary['issues']}</div>
        <div class="stat-lbl">Totale avvik</div>
    </div>
    <div class="stat critical">
        <div class="stat-val">{summary['critical']}</div>
        <div class="stat-lbl">Kritiske</div>
    </div>
    <div class="stat serious">
        <div class="stat-val">{summary['serious']}</div>
        <div class="stat-lbl">Alvorlige</div>
    </div>
    <div class="stat">
        <div class="stat-val">{summary['moderate']}</div>
        <div class="stat-lbl">Moderate</div>
    </div>
    <div class="stat">
        <div class="stat-val">{summary['minor']}</div>
        <div class="stat-lbl">Mindre</div>
    </div>
    <div class="stat good">
        <div class="stat-val">{summary['passed']}</div>
        <div class="stat-lbl">Bestått</div>
    </div>
</div>

<section>
    <h2>Virksomhetsinformasjon</h2>
    <div class="meta-grid">
        <div class="meta-item"><strong>Virksomhet</strong>{company['name']}</div>
        <div class="meta-item"><strong>Org.nr.</strong>{company['org_nr'] or 'Ikke oppgitt i CSV'}</div>
        <div class="meta-item"><strong>Kategori</strong>{company['category_name']}</div>
        <div class="meta-item"><strong>Kommune / Region</strong>{company['municipality']}, {company['region']}</div>
        <div class="meta-item"><strong>Nettsted</strong><a href="{company['url']}">{company['url']}</a></div>
        <div class="meta-item"><strong>Notater</strong>{company['notes'] or '—'}</div>
    </div>
</section>

<section>
    <h2>Avvik etter lovkrav og beste praksis</h2>
    {"<p><em>Ingen avvik funnet.</em></p>" if not any(by_criterion.values()) else f"""
    <table>
        <thead>
            <tr>
                <th>Alvorlighetsgrad</th>
                <th>Regel-ID</th>
                <th>Problem</th>
                <th>Løsning</th>
                <th>Selektor</th>
            </tr>
        </thead>
        <tbody>
            {issues_rows}
        </tbody>
    </table>"""}
</section>

<section>
    <h2>Bestått ({len(all_passed)} sjekker)</h2>
    <ul class="passed-list">
        {passed_list if passed_list else '<li>Ingen beståtte sjekker registrert</li>'}
    </ul>
</section>

{"" if not all_warnings else f'''
<section>
    <h2>Advarsler ({len(all_warnings)})</h2>
    <ul class="warn-list">
        {warn_list}
    </ul>
</section>
'''}

<div class="footer">
    Generert av Tilgjengelig Reiselivssjekker &mdash; Basert på norsk reiselivslovgivning og GDPR
</div>
</body>
</html>"""


def generate_summary_html(results: list, output_file: str):
    """Generate a county-level summary HTML with all company results."""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')

    total_sites    = len(results)
    successful     = sum(1 for r in results if r['status'] == 'success')
    total_issues   = sum(r['issues'] for r in results)
    total_critical = sum(r['critical'] for r in results)
    total_serious  = sum(r['serious'] for r in results)

    # Group by category
    by_category = {}
    for r in results:
        cat = r.get('category', 'Ukategorisert')
        by_category.setdefault(cat, []).append(r)

    category_sections = ""
    for cat, items in sorted(by_category.items()):
        rows = ""
        for r in sorted(items, key=lambda x: x['critical'], reverse=True):
            sev = _severity_class(r['critical'])
            link = f'<a href="{r["report_file"]}" class="report-btn">Se rapport</a>' \
                   if r.get('report_file') else '—'
            status_cls = 'good' if r['status'] == 'success' else 'critical'
            status_txt = 'OK' if r['status'] == 'success' else 'Feil'
            rows += f"""
            <tr>
                <td><a href="{r['url']}" target="_blank">{r['name']}</a></td>
                <td>{r['municipality']}</td>
                <td>{r['org_nr'] or '—'}</td>
                <td>{r['pages']}</td>
                <td><span class="badge {sev}">{r['critical']}</span></td>
                <td>{r['serious']}</td>
                <td>{r['moderate']}</td>
                <td>{r['issues']}</td>
                <td><span class="badge {status_cls}">{status_txt}</span></td>
                <td>{link}</td>
            </tr>"""

        category_sections += f"""
        <section>
            <h2>{cat} ({len(items)} virksomheter)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Virksomhet</th><th>Kommune</th><th>Org.nr</th>
                        <th>Sider</th><th>Kritisk</th><th>Alvorlig</th>
                        <th>Moderat</th><th>Totalt</th><th>Status</th><th>Rapport</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </section>"""

    html = f"""<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Finnmark Reiselivssjekk – Sammendrag</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                line-height: 1.6; max-width: 1400px; margin: 0 auto; padding: 20px;
                background: #f0f4f8; }}
        .header {{ background: linear-gradient(135deg, #1a3a5c, #0e5f8a);
                   color: white; padding: 30px; border-radius: 10px; margin-bottom: 24px; }}
        .header h1 {{ margin: 0 0 6px; }}
        .header p {{ margin: 4px 0; opacity: 0.85; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                  gap: 14px; margin-bottom: 24px; }}
        .stat {{ background: white; padding: 20px; border-radius: 8px; text-align: center;
                 box-shadow: 0 1px 4px rgba(0,0,0,0.1); }}
        .stat-val {{ font-size: 2.2em; font-weight: 700; }}
        .stat-lbl {{ color: #666; font-size: 0.85em; margin-top: 4px; }}
        .stat.critical .stat-val {{ color: #c00; }}
        .stat.serious  .stat-val {{ color: #e05800; }}
        .stat.good     .stat-val {{ color: #1a7a3c; }}
        section {{ background: white; border-radius: 8px; padding: 24px;
                   margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
        section h2 {{ color: #1a3a5c; margin-top: 0; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.91em; }}
        th {{ background: #1a3a5c; color: white; padding: 10px 12px; text-align: left; }}
        td {{ padding: 9px 12px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background: #f8fafc; }}
        .badge {{ display: inline-block; padding: 3px 8px; border-radius: 4px;
                  font-size: 0.82em; font-weight: 600; }}
        .badge.critical {{ background: #c00;    color: #fff; }}
        .badge.serious   {{ background: #e05800; color: #fff; }}
        .badge.moderate  {{ background: #f9a825; color: #333; }}
        .badge.minor     {{ background: #7cb9e8; color: #000; }}
        .badge.good      {{ background: #1a7a3c; color: #fff; }}
        .report-btn {{ padding: 5px 10px; background: #1a3a5c; color: white;
                       border-radius: 4px; text-decoration: none; font-size: 0.85em; }}
        .report-btn:hover {{ background: #0e5f8a; }}
        .footer {{ text-align: center; color: #888; padding: 20px; font-size: 0.85em; }}
    </style>
</head>
<body>

<div class="header">
    <h1>Finnmark Reiselivssjekk — Sammendrag</h1>
    <p>Automatisk sjekk av norske reiselivsbedrifter i Finnmark mot lovkrav og beste praksis</p>
    <p><strong>Skannet:</strong> {ts} &nbsp;|&nbsp;
       <strong>Regler:</strong> Markedsføringsloven, Angrerettloven, Pakkereiseloven, GDPR</p>
</div>

<div class="stats">
    <div class="stat">
        <div class="stat-val">{total_sites}</div>
        <div class="stat-lbl">Nettsteder</div>
    </div>
    <div class="stat good">
        <div class="stat-val">{successful}</div>
        <div class="stat-lbl">Vellykkede</div>
    </div>
    <div class="stat critical">
        <div class="stat-val">{total_critical}</div>
        <div class="stat-lbl">Kritiske avvik</div>
    </div>
    <div class="stat serious">
        <div class="stat-val">{total_serious}</div>
        <div class="stat-lbl">Alvorlige avvik</div>
    </div>
    <div class="stat">
        <div class="stat-val">{total_issues}</div>
        <div class="stat-lbl">Totale avvik</div>
    </div>
    <div class="stat">
        <div class="stat-val">{len(by_category)}</div>
        <div class="stat-lbl">Kategorier</div>
    </div>
</div>

{category_sections}

<div class="footer">
    Generert av Tilgjengelig Reiselivssjekker &mdash;
    Kategorier: Opplevelse, Overnatting, Transport, Mat, Guidede turer, Destinasjonsselskaper
</div>
</body>
</html>"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\nSammendrag lagret: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Batch travel compliance scanner for Finnmark businesses"
    )
    parser.add_argument('--category',   help='Filter by category name from CSV')
    parser.add_argument('--max-pages',  type=int, default=MAX_PAGES,
                        help=f'Max pages per site (default: {MAX_PAGES})')
    parser.add_argument('--csv',        default=CSV_FILE,
                        help=f'Path to CSV data file (default: {CSV_FILE})')
    args = parser.parse_args()

    print("=" * 60)
    print("  FINNMARK REISELIVSSJEKK — BATCH SKANNER")
    print("=" * 60)
    print(f"  Datakilde:   {args.csv}")
    print(f"  Maks sider:  {args.max_pages}")
    print(f"  Metode:      HTTP requests (ingen Playwright nødvendig)")
    if args.category:
        print(f"  Kategori:    {args.category}")
    print()

    # Load companies
    companies = load_companies(args.csv, category_filter=args.category)
    if not companies:
        print(f"Ingen virksomheter funnet i {args.csv}")
        return

    print(f"Fant {len(companies)} virksomheter å skanne\n")

    # Shared HTTP session (reused across all companies)
    session = http_requests.Session()
    session.headers.update({
        'User-Agent': 'TravelComplianceBot/1.0 (Tilgjengelig; WCAG + Reiseliv)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'nb,no,nn,en;q=0.5',
    })

    results = []
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for i, company in enumerate(companies, 1):
        print(f"\n[{i}/{len(companies)}]", end=" ")
        result = scan_company(company, session, args.max_pages)
        results.append(result)

        # Save intermediate JSON after each company
        with open(RESULTS_JSON, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    # Generate final summary report
    generate_summary_html(results, SUMMARY_HTML)

    # Final console summary
    print("\n" + "=" * 60)
    print("  SKANNING FULLFØRT")
    print("=" * 60)
    print(f"  Virksomheter skannet: {len(results)}")
    print(f"  Vellykkede:           {sum(1 for r in results if r['status'] == 'success')}")
    print(f"  Feilet:               {sum(1 for r in results if r['status'] == 'error')}")
    print(f"  Totale avvik:         {sum(r['issues'] for r in results)}")
    print(f"  Kritiske avvik:       {sum(r['critical'] for r in results)}")
    print()
    print(f"  Individuelle rapporter: {OUTPUT_DIR}/")
    print(f"  Sammendrag HTML:        {SUMMARY_HTML}")
    print(f"  JSON-data:              {RESULTS_JSON}")
    print("=" * 60)


if __name__ == "__main__":
    main()
