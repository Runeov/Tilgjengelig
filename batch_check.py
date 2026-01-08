#!/usr/bin/env python3
"""
WCAG Checker - Batch script for running WCAG checks on all Norwegian municipalities.
Reads URLs from counties.csv and runs checks on each municipality.

Features:
- Checks ALL municipalities (not just one per county)
- Includes accessibility statement (tilgjengelighetserklaring) check
- Can run statement-only quick check
- Generates summary report at the end
"""

import csv
import subprocess
import sys
import os
import json
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Configuration (relative to script location)
CSV_PATH = os.path.join(SCRIPT_DIR, "counties.csv")
CHECKER_SCRIPT = os.path.join(SCRIPT_DIR, "checker.py")
STATEMENT_SCRIPT = os.path.join(SCRIPT_DIR, "accessibility_statement.py")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "reports")

# Default checker parameters
DEFAULT_MAX_PAGES = 20
DEFAULT_OUTPUT_FORMAT = "html"
DEFAULT_EXCLUDE_PATTERNS = "/aktuelt/,/nyheter/,/artikkel/,/innhold/,/kunngjoring/,/arrangement/,/hendelse/,/dokument/,/fil/"


@dataclass
class MunicipalityResult:
    """Result for a single municipality check."""
    municipality_number: str
    municipality_name: str
    county_number: str
    county_name: str
    url: str
    has_statement: bool = False
    statement_url: Optional[str] = None
    statement_current: bool = False
    statement_last_updated: Optional[str] = None
    wcag_issues: int = 0
    wcag_critical: int = 0
    wcag_serious: int = 0
    report_file: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = ""


def sanitize_filename(name: str) -> str:
    """Sanitize a string to be used as a filename."""
    name = name.replace("/", "-")
    name = name.replace("\\", "-")
    name = name.replace(":", "-")
    name = name.replace(" ", "_")
    name = name.replace("æ", "ae")
    name = name.replace("ø", "o")
    name = name.replace("å", "aa")
    name = name.replace("Æ", "Ae")
    name = name.replace("Ø", "O")
    name = name.replace("Å", "Aa")
    return name


def get_all_municipalities(csv_path: str) -> List[dict]:
    """Read CSV and return list of all municipalities."""
    municipalities = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            municipalities.append({
                'county_number': row['County Number'].strip(),
                'county_name': row['County Name'].strip(),
                'municipality_number': row['Municipality Number'].strip(),
                'municipality_name': row['Municipality Name'].strip(),
                'url': row['Official Website'].strip()
            })
    
    return municipalities


def get_unique_counties(csv_path: str) -> List[dict]:
    """Read CSV and return list of unique counties (one municipality each)."""
    counties = {}
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            county_name = row['County Name'].strip()
            if county_name not in counties:
                counties[county_name] = {
                    'county_number': row['County Number'].strip(),
                    'county_name': county_name,
                    'municipality_number': row['Municipality Number'].strip(),
                    'municipality_name': row['Municipality Name'].strip(),
                    'url': row['Official Website'].strip()
                }
    
    return list(counties.values())


def check_statement_only(url: str) -> dict:
    """Run only the accessibility statement check (fast)."""
    try:
        # Import the checker directly for speed
        sys.path.insert(0, SCRIPT_DIR)
        from accessibility_statement import check_accessibility_statement
        
        result = check_accessibility_statement(url)
        return {
            'has_statement': result.has_statement_page,
            'statement_url': result.statement_page_url,
            'uustatus_url': result.uustatus_url,
            'is_current': result.is_current,
            'last_updated': result.last_updated,
            'days_since_update': result.days_since_update,
            'compliance_level': result.compliance_level,
            'errors': result.errors,
            'warnings': result.warnings
        }
    except Exception as e:
        return {
            'has_statement': False,
            'error': str(e)
        }


def run_full_wcag_check(municipality: dict, max_pages: int, output_format: str, 
                        output_dir: str, exclude_patterns: str) -> MunicipalityResult:
    """Run full WCAG check including accessibility statement."""
    safe_name = sanitize_filename(municipality['municipality_name'])
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = os.path.join(output_dir, f"wcag_{safe_name}_{timestamp}.{output_format}")
    
    result = MunicipalityResult(
        municipality_number=municipality['municipality_number'],
        municipality_name=municipality['municipality_name'],
        county_number=municipality['county_number'],
        county_name=municipality['county_name'],
        url=municipality['url'],
        timestamp=datetime.now().isoformat()
    )
    
    # Build the command
    cmd = [
        sys.executable,
        CHECKER_SCRIPT,
        municipality['url'],
        "--max-pages", str(max_pages),
        "--format", output_format,
        "--exclude", exclude_patterns,
        "--output", output_filename
    ]
    
    print(f"\n{'='*60}")
    print(f"Checking: {municipality['municipality_name']} ({municipality['county_name']})")
    print(f"URL: {municipality['url']}")
    print(f"{'='*60}")
    
    # Set environment for proper encoding on Windows
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    
    try:
        # Use encoding='utf-8' for Windows compatibility with Norwegian characters
        proc_result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=300,
            encoding='utf-8',
            errors='replace',
            env=env
        )
        
        if proc_result.returncode != 0:
            result.error = proc_result.stderr[:500] if proc_result.stderr else "Unknown error"
            print(f"Error: {result.error}")
        else:
            print(proc_result.stdout)
            result.report_file = output_filename
            
            # Try to extract summary from output
            output = proc_result.stdout
            if "Critical:" in output:
                try:
                    for line in output.split('\n'):
                        if 'Critical:' in line:
                            result.wcag_critical = int(line.split(':')[1].strip())
                        elif 'Serious:' in line:
                            result.wcag_serious = int(line.split(':')[1].strip())
                        elif 'Found' in line and 'issues' in line:
                            parts = line.split()
                            for i, p in enumerate(parts):
                                if p == 'Found' and i+1 < len(parts):
                                    result.wcag_issues = int(parts[i+1])
                except:
                    pass
            
            # Check for statement info in output
            if "Tilgjengelighetserklaring funnet" in output or "[OK] Tilgjengelighetserklaring" in output:
                result.has_statement = True
            if "Sist oppdatert:" in output:
                result.statement_current = "[OK]" in output.split("Sist oppdatert:")[0].split('\n')[-1]
                
    except subprocess.TimeoutExpired:
        result.error = "Timeout (5 minutes)"
        print(f"Error: Timeout after 5 minutes")
    except Exception as e:
        result.error = str(e)
        print(f"Error: {e}")
    
    return result


def run_statement_check(municipality: dict) -> MunicipalityResult:
    """Run only accessibility statement check (fast mode)."""
    result = MunicipalityResult(
        municipality_number=municipality['municipality_number'],
        municipality_name=municipality['municipality_name'],
        county_number=municipality['county_number'],
        county_name=municipality['county_name'],
        url=municipality['url'],
        timestamp=datetime.now().isoformat()
    )
    
    print(f"Checking statement: {municipality['municipality_name']}... ", end='', flush=True)
    
    try:
        stmt = check_statement_only(municipality['url'])
        result.has_statement = stmt.get('has_statement', False)
        result.statement_url = stmt.get('statement_url') or stmt.get('uustatus_url')
        result.statement_current = stmt.get('is_current', False)
        result.statement_last_updated = stmt.get('last_updated')
        
        if result.has_statement and result.statement_current:
            print("[OK] Current")
        elif result.has_statement:
            print(f"[!] Outdated ({result.statement_last_updated})")
        else:
            print("[X] Missing")
            
        if stmt.get('error'):
            result.error = stmt['error']
            
    except Exception as e:
        result.error = str(e)
        print(f"[X] Error: {e}")
    
    return result


def generate_summary_report(results: List[MunicipalityResult], output_dir: str, mode: str) -> str:
    """Generate a summary report of all checks."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Count statistics
    total = len(results)
    with_statement = sum(1 for r in results if r.has_statement)
    statement_current = sum(1 for r in results if r.statement_current)
    errors = sum(1 for r in results if r.error)
    
    # Group by county
    by_county = {}
    for r in results:
        if r.county_name not in by_county:
            by_county[r.county_name] = []
        by_county[r.county_name].append(r)
    
    # Generate HTML summary
    html = f"""<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WCAG Batch Check Summary - {timestamp}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               line-height: 1.6; max-width: 1400px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        h1, h2, h3 {{ color: #1a1a2e; }}
        .header {{ background: #003366; color: white; padding: 30px; border-radius: 8px; margin-bottom: 20px; }}
        .header h1 {{ margin: 0; color: white; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .stat {{ background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-value {{ font-size: 2.5em; font-weight: bold; }}
        .stat-label {{ color: #666; }}
        .success {{ background: #e8f5e9; color: #2e7d32; }}
        .warning {{ background: #fff3e0; color: #e65100; }}
        .error {{ background: #fee; color: #c00; }}
        .county-section {{ background: white; border-radius: 8px; margin: 20px 0; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .county-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #003366; padding-bottom: 10px; margin-bottom: 15px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f5f5f5; font-weight: 600; }}
        tr:hover {{ background: #f9f9f9; }}
        .status-badge {{ padding: 4px 10px; border-radius: 4px; font-size: 0.85em; font-weight: 500; }}
        .status-ok {{ background: #e8f5e9; color: #2e7d32; }}
        .status-warn {{ background: #fff3e0; color: #e65100; }}
        .status-error {{ background: #fee; color: #c00; }}
        a {{ color: #003366; }}
        .filter-bar {{ background: white; padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .filter-bar label {{ margin-right: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 WCAG Batch Check Summary</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Mode: {'Full WCAG Check' if mode == 'full' else 'Statement Only Check'}</p>
    </div>
    
    <div class="summary">
        <div class="stat">
            <div class="stat-value">{total}</div>
            <div class="stat-label">Total Municipalities</div>
        </div>
        <div class="stat success">
            <div class="stat-value">{with_statement}</div>
            <div class="stat-label">Has Statement</div>
        </div>
        <div class="stat {'success' if statement_current > total * 0.8 else 'warning'}">
            <div class="stat-value">{statement_current}</div>
            <div class="stat-label">Statement Current</div>
        </div>
        <div class="stat warning">
            <div class="stat-value">{total - with_statement}</div>
            <div class="stat-label">Missing Statement</div>
        </div>
        <div class="stat {'error' if errors > 0 else ''}">
            <div class="stat-value">{errors}</div>
            <div class="stat-label">Errors</div>
        </div>
    </div>
    
    <div class="filter-bar">
        <strong>Quick Stats:</strong>
        {with_statement}/{total} ({with_statement*100//total if total > 0 else 0}%) har tilgjengelighetserklaring |
        {statement_current}/{total} ({statement_current*100//total if total > 0 else 0}%) har oppdatert erklaring
    </div>
"""
    
    # Add county sections
    for county_name in sorted(by_county.keys()):
        municipalities = by_county[county_name]
        county_with_stmt = sum(1 for m in municipalities if m.has_statement)
        county_current = sum(1 for m in municipalities if m.statement_current)
        
        html += f"""
    <div class="county-section">
        <div class="county-header">
            <h2>{county_name}</h2>
            <div>
                <span class="status-badge status-ok">{county_with_stmt}/{len(municipalities)} har erklaring</span>
                <span class="status-badge {'status-ok' if county_current == len(municipalities) else 'status-warn'}">{county_current}/{len(municipalities)} oppdatert</span>
            </div>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Kommune</th>
                    <th>Nettsted</th>
                    <th>Erklaring</th>
                    <th>Status</th>
                    <th>Sist oppdatert</th>
"""
        if mode == 'full':
            html += """                    <th>WCAG Avvik</th>
                    <th>Rapport</th>
"""
        html += """                </tr>
            </thead>
            <tbody>
"""
        
        for m in sorted(municipalities, key=lambda x: x.municipality_name):
            stmt_status = "status-ok" if m.has_statement else "status-error"
            stmt_text = "Ja" if m.has_statement else "Nei"
            
            current_status = ""
            if m.has_statement:
                if m.statement_current:
                    current_status = '<span class="status-badge status-ok">Oppdatert</span>'
                else:
                    current_status = '<span class="status-badge status-warn">Utdatert</span>'
            
            html += f"""                <tr>
                    <td><strong>{m.municipality_name}</strong></td>
                    <td><a href="{m.url}" target="_blank">{m.url}</a></td>
                    <td><span class="status-badge {stmt_status}">{stmt_text}</span></td>
                    <td>{current_status}</td>
                    <td>{m.statement_last_updated or '-'}</td>
"""
            if mode == 'full':
                issues_badge = ""
                if m.wcag_critical > 0:
                    issues_badge = f'<span class="status-badge status-error">{m.wcag_issues} ({m.wcag_critical} kritiske)</span>'
                elif m.wcag_issues > 0:
                    issues_badge = f'<span class="status-badge status-warn">{m.wcag_issues}</span>'
                else:
                    issues_badge = '<span class="status-badge status-ok">0</span>'
                
                report_link = f'<a href="{os.path.basename(m.report_file)}" target="_blank">📄 Rapport</a>' if m.report_file else '-'
                html += f"""                    <td>{issues_badge}</td>
                    <td>{report_link}</td>
"""
            html += """                </tr>
"""
        
        html += """            </tbody>
        </table>
    </div>
"""
    
    html += """
</body>
</html>
"""
    
    # Save HTML summary
    summary_file = os.path.join(output_dir, f"batch_summary_{timestamp}.html")
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    # Also save JSON for further processing
    json_file = os.path.join(output_dir, f"batch_summary_{timestamp}.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': timestamp,
            'mode': mode,
            'total': total,
            'with_statement': with_statement,
            'statement_current': statement_current,
            'errors': errors,
            'results': [asdict(r) for r in results]
        }, f, indent=2, ensure_ascii=False)
    
    return summary_file


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='WCAG Batch Checker for Norwegian Municipalities',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check all municipalities (full WCAG + statement)
  python batch_check.py --all
  
  # Quick statement-only check for all municipalities
  python batch_check.py --all --statement-only
  
  # Check one municipality per county (faster for testing)
  python batch_check.py --counties-only
  
  # Check specific county
  python batch_check.py --county "Oslo"
  
  # Check specific municipality
  python batch_check.py --municipality "Trondheim"
        """
    )
    
    parser.add_argument('--all', action='store_true',
                        help='Check ALL municipalities')
    parser.add_argument('--counties-only', action='store_true',
                        help='Check one municipality per county (faster)')
    parser.add_argument('--county', type=str,
                        help='Check only municipalities in specific county')
    parser.add_argument('--municipality', type=str,
                        help='Check only specific municipality')
    parser.add_argument('--statement-only', action='store_true',
                        help='Only check accessibility statement (fast mode)')
    parser.add_argument('--max-pages', type=int, default=DEFAULT_MAX_PAGES,
                        help=f'Max pages to check per site (default: {DEFAULT_MAX_PAGES})')
    parser.add_argument('--format', choices=['html', 'json', 'markdown'], 
                        default=DEFAULT_OUTPUT_FORMAT,
                        help=f'Output format (default: {DEFAULT_OUTPUT_FORMAT})')
    parser.add_argument('--output-dir', type=str, default=OUTPUT_DIR,
                        help=f'Output directory (default: {OUTPUT_DIR})')
    parser.add_argument('--csv', type=str, default=CSV_PATH,
                        help=f'Path to CSV file (default: {CSV_PATH})')
    
    args = parser.parse_args()
    
    # Determine which municipalities to check
    if args.municipality:
        all_municipalities = get_all_municipalities(args.csv)
        municipalities = [m for m in all_municipalities 
                         if args.municipality.lower() in m['municipality_name'].lower()]
        if not municipalities:
            print(f"Municipality '{args.municipality}' not found")
            sys.exit(1)
    elif args.county:
        all_municipalities = get_all_municipalities(args.csv)
        municipalities = [m for m in all_municipalities 
                         if args.county.lower() in m['county_name'].lower()]
        if not municipalities:
            print(f"County '{args.county}' not found")
            sys.exit(1)
    elif args.counties_only:
        municipalities = get_unique_counties(args.csv)
    elif args.all:
        municipalities = get_all_municipalities(args.csv)
    else:
        # Default: one per county
        municipalities = get_unique_counties(args.csv)
        print("No filter specified, defaulting to --counties-only mode")
        print("Use --all to check all municipalities")
    
    mode = 'statement' if args.statement_only else 'full'
    
    print("=" * 60)
    print("WCAG Batch Checker for Norwegian Municipalities")
    print("=" * 60)
    print(f"Mode: {'Statement only (fast)' if args.statement_only else 'Full WCAG check'}")
    print(f"Municipalities to check: {len(municipalities)}")
    print(f"Output directory: {args.output_dir}")
    if not args.statement_only:
        print(f"Max pages per site: {args.max_pages}")
    print("=" * 60)
    print()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Run checks
    results = []
    
    for i, municipality in enumerate(municipalities, 1):
        print(f"\n[{i}/{len(municipalities)}] ", end='')
        
        if args.statement_only:
            result = run_statement_check(municipality)
        else:
            result = run_full_wcag_check(
                municipality, 
                args.max_pages, 
                args.format,
                args.output_dir,
                DEFAULT_EXCLUDE_PATTERNS
            )
        
        results.append(result)
    
    # Generate summary report
    print("\n" + "=" * 60)
    print("Generating summary report...")
    summary_file = generate_summary_report(results, args.output_dir, mode)
    
    print("=" * 60)
    print("BATCH CHECK COMPLETE")
    print("=" * 60)
    print(f"Total checked: {len(results)}")
    print(f"With statement: {sum(1 for r in results if r.has_statement)}")
    print(f"Statement current: {sum(1 for r in results if r.statement_current)}")
    print(f"Errors: {sum(1 for r in results if r.error)}")
    print(f"\nSummary report: {summary_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
