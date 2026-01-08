#!/usr/bin/env python3
"""
WCAG Report Analyzer
Reads batch summary JSON files and generates comprehensive overview reports
with expandable sections and links to individual municipality reports.
"""

import json
import sys
import os
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict

def load_summary(json_path: str) -> Dict[str, Any]:
    """Load the batch summary JSON file."""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_results(data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze the results and compute statistics."""
    results = data['results']
    
    total = len(results)
    with_statement = sum(1 for r in results if r['has_statement'])
    without_statement = total - with_statement
    statement_current = sum(1 for r in results if r['statement_current'])
    errors = sum(1 for r in results if r['error'])
    
    total_issues = sum(r['wcag_issues'] for r in results)
    total_critical = sum(r['wcag_critical'] for r in results)
    total_serious = sum(r['wcag_serious'] for r in results)
    
    with_issues = [r for r in results if r['wcag_issues'] > 0]
    with_critical = [r for r in results if r['wcag_critical'] > 0]
    zero_issues = [r for r in results if r['wcag_issues'] == 0]
    
    avg_issues = total_issues / len(with_issues) if with_issues else 0
    
    by_county = defaultdict(list)
    for r in results:
        by_county[r['county_name']].append(r)
    
    county_stats = {}
    for county, munis in by_county.items():
        county_stats[county] = {
            'total': len(munis),
            'with_statement': sum(1 for m in munis if m['has_statement']),
            'without_statement': sum(1 for m in munis if not m['has_statement']),
            'total_issues': sum(m['wcag_issues'] for m in munis),
            'total_critical': sum(m['wcag_critical'] for m in munis),
            'total_serious': sum(m['wcag_serious'] for m in munis),
            'avg_issues': sum(m['wcag_issues'] for m in munis) / len(munis),
            'municipalities': sorted(munis, key=lambda x: x['wcag_issues'], reverse=True)
        }
    
    missing_statement = [r for r in results if not r['has_statement']]
    
    return {
        'overview': {
            'total_municipalities': total,
            'with_statement': with_statement,
            'without_statement': without_statement,
            'statement_percentage': round(with_statement / total * 100, 1),
            'statement_current': statement_current,
            'errors': errors,
            'total_issues': total_issues,
            'total_critical': total_critical,
            'total_serious': total_serious,
            'avg_issues_per_municipality': round(avg_issues, 1),
            'municipalities_with_issues': len(with_issues),
            'municipalities_zero_issues': len(zero_issues),
            'municipalities_with_critical': len(with_critical),
        },
        'county_stats': county_stats,
        'missing_statement': missing_statement,
        'zero_issues': zero_issues,
        'all_results': sorted(results, key=lambda x: (x['county_name'], x['municipality_name']))
    }

def get_report_filename(report_path: str) -> str:
    """Extract just the filename from a full path."""
    if report_path:
        return os.path.basename(report_path)
    return None

def print_report(data: Dict[str, Any], analysis: Dict[str, Any]):
    """Print a formatted text report."""
    overview = analysis['overview']
    
    print("=" * 70)
    print("WCAG BATCH CHECK - ANALYSIS REPORT")
    print("=" * 70)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Data from: {data.get('timestamp', 'Unknown')}")
    print()
    print(f"Total municipalities:    {overview['total_municipalities']}")
    print(f"With statement:          {overview['with_statement']} ({overview['statement_percentage']}%)")
    print(f"Missing statement:       {overview['without_statement']}")
    print(f"Total issues:            {overview['total_issues']:,}")
    print(f"Critical issues:         {overview['total_critical']:,}")
    print(f"Average per municipality: {overview['avg_issues_per_municipality']}")
    print("=" * 70)

def generate_html_report(data: Dict[str, Any], analysis: Dict[str, Any], output_path: str, reports_dir: str = None):
    """Generate an HTML overview report with expandable sections."""
    overview = analysis['overview']
    county_stats = analysis['county_stats']
    
    if reports_dir is None:
        reports_dir = "."
    
    html = f"""<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WCAG Analysis Report - Norwegian Municipalities</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            line-height: 1.6; max-width: 1400px; margin: 0 auto; padding: 20px; background: #f5f5f5; 
        }}
        h1, h2, h3 {{ color: #1a1a2e; }}
        a {{ color: #003366; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        
        .header {{ 
            background: linear-gradient(135deg, #003366, #004488); 
            color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px;
        }}
        .header h1 {{ margin: 0 0 10px 0; color: white; font-size: 2em; }}
        .header p {{ margin: 5px 0; opacity: 0.9; }}
        
        .stats-grid {{ 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); 
            gap: 20px; margin-bottom: 30px; 
        }}
        .stat-card {{ 
            background: white; padding: 25px; border-radius: 12px; text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-value {{ font-size: 2.2em; font-weight: bold; margin-bottom: 5px; }}
        .stat-label {{ color: #666; font-size: 0.9em; }}
        .stat-good {{ color: #2e7d32; }}
        .stat-warn {{ color: #e65100; }}
        .stat-bad {{ color: #c62828; }}
        
        .section {{ 
            background: white; border-radius: 12px; padding: 25px; margin-bottom: 25px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{ margin-top: 0; padding-bottom: 15px; border-bottom: 2px solid #003366; }}
        
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; color: #333; position: sticky; top: 0; }}
        tr:hover {{ background: #f8f9fa; }}
        
        .badge {{ 
            display: inline-block; padding: 4px 12px; border-radius: 20px; 
            font-size: 0.85em; font-weight: 500; 
        }}
        .badge-good {{ background: #e8f5e9; color: #2e7d32; }}
        .badge-warn {{ background: #fff3e0; color: #e65100; }}
        .badge-bad {{ background: #ffebee; color: #c62828; }}
        
        .expandable {{ border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 10px; overflow: hidden; }}
        .expandable-header {{ 
            background: #f8f9fa; padding: 15px 20px; cursor: pointer;
            display: flex; justify-content: space-between; align-items: center;
        }}
        .expandable-header:hover {{ background: #e8e8e8; }}
        .expandable-header h3 {{ margin: 0; font-size: 1.1em; }}
        .expandable-stats {{ display: flex; gap: 15px; font-size: 0.9em; }}
        .expandable-stats span {{ padding: 4px 10px; background: white; border-radius: 4px; }}
        .expandable-icon {{ font-size: 1.5em; transition: transform 0.3s; color: #666; }}
        .expandable.open .expandable-icon {{ transform: rotate(180deg); }}
        .expandable-content {{ display: none; padding: 0; max-height: 500px; overflow-y: auto; }}
        .expandable.open .expandable-content {{ display: block; }}
        .expandable-content table {{ margin: 0; }}
        .expandable-content th {{ background: #003366; color: white; }}
        
        .link-btn {{
            display: inline-block; padding: 4px 10px; background: #003366; color: white !important;
            border-radius: 4px; font-size: 0.85em; margin: 2px;
        }}
        .link-btn:hover {{ background: #004488; text-decoration: none; }}
        .link-btn.secondary {{ background: #666; }}
        .link-btn.secondary:hover {{ background: #888; }}
        
        .filter-bar {{ display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; }}
        .filter-bar input, .filter-bar select {{
            padding: 10px 15px; border: 1px solid #ddd; border-radius: 8px; font-size: 1em;
        }}
        .filter-bar input {{ flex: 1; min-width: 200px; }}
        
        .nav-tabs {{ display: flex; gap: 5px; margin-bottom: 20px; border-bottom: 2px solid #e0e0e0; }}
        .nav-tab {{
            padding: 12px 20px; cursor: pointer; border: none; background: none;
            font-size: 1em; color: #666; border-bottom: 3px solid transparent; margin-bottom: -2px;
        }}
        .nav-tab:hover {{ color: #003366; }}
        .nav-tab.active {{ color: #003366; border-bottom-color: #003366; font-weight: 600; }}
        
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        
        @media (max-width: 768px) {{
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .expandable-stats {{ flex-wrap: wrap; gap: 8px; }}
            .filter-bar {{ flex-direction: column; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>WCAG Compliance Analysis Report</h1>
        <p>Norwegian Municipalities - Accessibility Check Results</p>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Data: {data.get('timestamp', 'Unknown')}</p>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value">{overview['total_municipalities']}</div>
            <div class="stat-label">Municipalities</div>
        </div>
        <div class="stat-card">
            <div class="stat-value stat-good">{overview['with_statement']}</div>
            <div class="stat-label">Have Statement ({overview['statement_percentage']}%)</div>
        </div>
        <div class="stat-card">
            <div class="stat-value stat-warn">{overview['without_statement']}</div>
            <div class="stat-label">Missing Statement</div>
        </div>
        <div class="stat-card">
            <div class="stat-value stat-bad">{overview['total_issues']:,}</div>
            <div class="stat-label">Total Issues</div>
        </div>
        <div class="stat-card">
            <div class="stat-value stat-bad">{overview['total_critical']:,}</div>
            <div class="stat-label">Critical Issues</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{overview['avg_issues_per_municipality']}</div>
            <div class="stat-label">Avg per Municipality</div>
        </div>
    </div>
    
    <div class="section">
        <div class="nav-tabs">
            <button class="nav-tab active" onclick="showTab('counties')">By County</button>
            <button class="nav-tab" onclick="showTab('worst')">Worst</button>
            <button class="nav-tab" onclick="showTab('best')">Best</button>
            <button class="nav-tab" onclick="showTab('missing')">Missing Statement</button>
            <button class="nav-tab" onclick="showTab('all')">All Municipalities</button>
        </div>
        
        <!-- Counties Tab -->
        <div id="tab-counties" class="tab-content active">
            <h2>Results by County</h2>
            <p>Click on a county to expand and see all municipalities with links to their reports</p>
"""
    
    sorted_counties = sorted(county_stats.items(), key=lambda x: x[1]['total_issues'], reverse=True)
    
    for county, stats in sorted_counties:
        stmt_pct = round(stats['with_statement'] / stats['total'] * 100)
        badge_class = 'badge-good' if stmt_pct >= 80 else ('badge-warn' if stmt_pct >= 50 else 'badge-bad')
        
        html += f"""
            <div class="expandable" id="county-{county.replace(' ', '-')}">
                <div class="expandable-header" onclick="toggleExpand(this.parentElement)">
                    <h3>{county}</h3>
                    <div class="expandable-stats">
                        <span>{stats['total']} kommuner</span>
                        <span class="{badge_class}">{stats['with_statement']}/{stats['total']} statement</span>
                        <span class="badge-bad">{stats['total_issues']:,} issues</span>
                        <span>{stats['total_critical']:,} critical</span>
                    </div>
                    <span class="expandable-icon">&#9660;</span>
                </div>
                <div class="expandable-content">
                    <table>
                        <thead>
                            <tr>
                                <th>Municipality</th>
                                <th>Issues</th>
                                <th>Critical</th>
                                <th>Serious</th>
                                <th>Statement</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
"""
        
        for m in stats['municipalities']:
            stmt_badge = 'badge-good' if m['has_statement'] else 'badge-bad'
            stmt_text = 'Yes' if m['has_statement'] else 'No'
            issues_badge = 'badge-bad' if m['wcag_critical'] > 0 else ('badge-warn' if m['wcag_issues'] > 50 else 'badge-good')
            
            report_file = get_report_filename(m.get('report_file'))
            report_link = f'<a href="{reports_dir}/{report_file}" class="link-btn" target="_blank">View Report</a>' if report_file else ''
            stmt_link = ''
            if m.get('statement_url'):
                stmt_link = f'<a href="{m["statement_url"]}" class="link-btn secondary" target="_blank">Statement</a>'
            
            html += f"""
                            <tr>
                                <td><strong>{m['municipality_name']}</strong></td>
                                <td><span class="badge {issues_badge}">{m['wcag_issues']:,}</span></td>
                                <td>{m['wcag_critical']:,}</td>
                                <td>{m['wcag_serious']:,}</td>
                                <td><span class="badge {stmt_badge}">{stmt_text}</span></td>
                                <td>
                                    <a href="{m['url']}" class="link-btn secondary" target="_blank">Website</a>
                                    {report_link}
                                    {stmt_link}
                                </td>
                            </tr>
"""
        
        html += """
                        </tbody>
                    </table>
                </div>
            </div>
"""
    
    # Worst Tab
    html += """
        </div>
        <div id="tab-worst" class="tab-content">
            <h2>Top 20 Municipalities with Most Issues</h2>
            <table>
                <thead>
                    <tr><th>#</th><th>Municipality</th><th>County</th><th>Total</th><th>Critical</th><th>Serious</th><th>Actions</th></tr>
                </thead>
                <tbody>
"""
    
    worst_20 = sorted(analysis['all_results'], key=lambda x: x['wcag_issues'], reverse=True)[:20]
    for i, m in enumerate(worst_20, 1):
        report_file = get_report_filename(m.get('report_file'))
        report_link = f'<a href="{reports_dir}/{report_file}" class="link-btn" target="_blank">Report</a>' if report_file else ''
        
        html += f"""
                    <tr>
                        <td>{i}</td>
                        <td><strong>{m['municipality_name']}</strong></td>
                        <td>{m['county_name']}</td>
                        <td><span class="badge badge-bad">{m['wcag_issues']:,}</span></td>
                        <td>{m['wcag_critical']:,}</td>
                        <td>{m['wcag_serious']:,}</td>
                        <td>
                            <a href="{m['url']}" class="link-btn secondary" target="_blank">Website</a>
                            {report_link}
                        </td>
                    </tr>
"""
    
    html += """
                </tbody>
            </table>
            <h2 style="margin-top: 40px;">Top 20 with Most Critical Issues</h2>
            <table>
                <thead>
                    <tr><th>#</th><th>Municipality</th><th>County</th><th>Critical</th><th>Total</th><th>Actions</th></tr>
                </thead>
                <tbody>
"""
    
    worst_critical = sorted(analysis['all_results'], key=lambda x: x['wcag_critical'], reverse=True)[:20]
    for i, m in enumerate(worst_critical, 1):
        report_file = get_report_filename(m.get('report_file'))
        report_link = f'<a href="{reports_dir}/{report_file}" class="link-btn" target="_blank">Report</a>' if report_file else ''
        
        html += f"""
                    <tr>
                        <td>{i}</td>
                        <td><strong>{m['municipality_name']}</strong></td>
                        <td>{m['county_name']}</td>
                        <td><span class="badge badge-bad">{m['wcag_critical']:,}</span></td>
                        <td>{m['wcag_issues']:,}</td>
                        <td>
                            <a href="{m['url']}" class="link-btn secondary" target="_blank">Website</a>
                            {report_link}
                        </td>
                    </tr>
"""
    
    # Best Tab
    html += """
                </tbody>
            </table>
        </div>
        <div id="tab-best" class="tab-content">
            <h2>Top 20 Best Municipalities (Fewest Issues)</h2>
            <table>
                <thead>
                    <tr><th>#</th><th>Municipality</th><th>County</th><th>Issues</th><th>Critical</th><th>Statement</th><th>Actions</th></tr>
                </thead>
                <tbody>
"""
    
    best_20 = sorted([r for r in analysis['all_results'] if r['wcag_issues'] > 0], key=lambda x: x['wcag_issues'])[:20]
    for i, m in enumerate(best_20, 1):
        stmt_badge = 'badge-good' if m['has_statement'] else 'badge-bad'
        stmt_text = 'Yes' if m['has_statement'] else 'No'
        report_file = get_report_filename(m.get('report_file'))
        report_link = f'<a href="{reports_dir}/{report_file}" class="link-btn" target="_blank">Report</a>' if report_file else ''
        
        html += f"""
                    <tr>
                        <td>{i}</td>
                        <td><strong>{m['municipality_name']}</strong></td>
                        <td>{m['county_name']}</td>
                        <td><span class="badge badge-good">{m['wcag_issues']}</span></td>
                        <td>{m['wcag_critical']}</td>
                        <td><span class="badge {stmt_badge}">{stmt_text}</span></td>
                        <td>
                            <a href="{m['url']}" class="link-btn secondary" target="_blank">Website</a>
                            {report_link}
                        </td>
                    </tr>
"""
    
    # Missing Statement Tab
    html += f"""
                </tbody>
            </table>
        </div>
        <div id="tab-missing" class="tab-content">
            <h2>Municipalities Missing Accessibility Statement ({len(analysis['missing_statement'])})</h2>
            <table>
                <thead>
                    <tr><th>Municipality</th><th>County</th><th>WCAG Issues</th><th>Actions</th></tr>
                </thead>
                <tbody>
"""
    
    for m in sorted(analysis['missing_statement'], key=lambda x: (x['county_name'], x['municipality_name'])):
        report_file = get_report_filename(m.get('report_file'))
        report_link = f'<a href="{reports_dir}/{report_file}" class="link-btn" target="_blank">Report</a>' if report_file else ''
        
        html += f"""
                    <tr>
                        <td><strong>{m['municipality_name']}</strong></td>
                        <td>{m['county_name']}</td>
                        <td>{m['wcag_issues']:,}</td>
                        <td>
                            <a href="{m['url']}" class="link-btn secondary" target="_blank">Website</a>
                            {report_link}
                        </td>
                    </tr>
"""
    
    # All Municipalities Tab
    html += """
                </tbody>
            </table>
        </div>
        <div id="tab-all" class="tab-content">
            <h2>All Municipalities</h2>
            <div class="filter-bar">
                <input type="text" id="searchInput" placeholder="Search municipality..." onkeyup="filterTable()">
                <select id="countyFilter" onchange="filterTable()">
                    <option value="">All Counties</option>
"""
    
    for county in sorted(county_stats.keys()):
        html += f'                    <option value="{county}">{county}</option>\n'
    
    html += """
                </select>
                <select id="statementFilter" onchange="filterTable()">
                    <option value="">All</option>
                    <option value="yes">Has Statement</option>
                    <option value="no">Missing Statement</option>
                </select>
            </div>
            <table id="allTable">
                <thead>
                    <tr><th>Municipality</th><th>County</th><th>Issues</th><th>Critical</th><th>Statement</th><th>Actions</th></tr>
                </thead>
                <tbody>
"""
    
    for m in analysis['all_results']:
        stmt_badge = 'badge-good' if m['has_statement'] else 'badge-bad'
        stmt_text = 'Yes' if m['has_statement'] else 'No'
        stmt_data = 'yes' if m['has_statement'] else 'no'
        issues_badge = 'badge-bad' if m['wcag_critical'] > 0 else ('badge-warn' if m['wcag_issues'] > 50 else 'badge-good')
        report_file = get_report_filename(m.get('report_file'))
        report_link = f'<a href="{reports_dir}/{report_file}" class="link-btn" target="_blank">Report</a>' if report_file else ''
        
        html += f"""
                    <tr data-county="{m['county_name']}" data-statement="{stmt_data}">
                        <td><strong>{m['municipality_name']}</strong></td>
                        <td>{m['county_name']}</td>
                        <td><span class="badge {issues_badge}">{m['wcag_issues']:,}</span></td>
                        <td>{m['wcag_critical']:,}</td>
                        <td><span class="badge {stmt_badge}">{stmt_text}</span></td>
                        <td>
                            <a href="{m['url']}" class="link-btn secondary" target="_blank">Website</a>
                            {report_link}
                        </td>
                    </tr>
"""
    
    html += """
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        function toggleExpand(el) { el.classList.toggle('open'); }
        
        function showTab(name) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
            document.getElementById('tab-' + name).classList.add('active');
            event.target.classList.add('active');
        }
        
        function filterTable() {
            const search = document.getElementById('searchInput').value.toLowerCase();
            const county = document.getElementById('countyFilter').value;
            const stmt = document.getElementById('statementFilter').value;
            
            document.querySelectorAll('#allTable tbody tr').forEach(row => {
                const name = row.cells[0].textContent.toLowerCase();
                const match = name.includes(search) && 
                    (!county || row.dataset.county === county) &&
                    (!stmt || row.dataset.statement === stmt);
                row.style.display = match ? '' : 'none';
            });
        }
        
        // Auto-expand from URL hash
        if (location.hash) {
            const el = document.querySelector(location.hash);
            if (el) { el.classList.add('open'); el.scrollIntoView(); }
        }
    </script>
</body>
</html>
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return output_path

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze WCAG batch summary reports')
    parser.add_argument('json_file', help='Path to batch_summary JSON file')
    parser.add_argument('--html', type=str, help='Output HTML report path')
    parser.add_argument('--reports-dir', type=str, default='.', help='Directory containing individual reports (for links)')
    parser.add_argument('--quiet', '-q', action='store_true', help='Only generate files, no console output')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.json_file):
        print(f"Error: File not found: {args.json_file}")
        sys.exit(1)
    
    print(f"Loading: {args.json_file}")
    data = load_summary(args.json_file)
    
    print(f"Analyzing {len(data['results'])} municipalities...")
    analysis = analyze_results(data)
    
    if not args.quiet:
        print()
        print_report(data, analysis)
    
    if args.html:
        html_path = args.html
    else:
        base = os.path.splitext(args.json_file)[0]
        html_path = f"{base}_analysis.html"
    
    generate_html_report(data, analysis, html_path, args.reports_dir)
    print(f"\nHTML report saved to: {html_path}")

if __name__ == "__main__":
    main()
