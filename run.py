#!/usr/bin/env python3
"""
WCAG 2.1 Compliance Checker - Command Line Interface

Usage:
    python run.py <url> [options]

Examples:
    python run.py https://example.com
    python run.py https://example.com --max-pages 20 --format html
    python run.py https://example.com --output report.html
"""

import argparse
import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checker import WCAGChecker


def print_banner():
    """Print welcome banner."""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║              WCAG 2.1 Compliance Checker v1.0                 ║
║        Automated Website Accessibility Testing Tool           ║
╚═══════════════════════════════════════════════════════════════╝
""")


def print_progress(message):
    """Print progress message."""
    print(f"  → {message}")


def print_summary(result):
    """Print summary of results."""
    summary = result.summary
    
    print("\n" + "═" * 60)
    print("                    SCAN COMPLETE")
    print("═" * 60)
    print(f"""
  Pages Checked:    {summary['pages_checked']}
  Total Issues:     {summary['issues']}
  
  By Severity:
    • Critical:     {summary['critical']}
    • Serious:      {summary['serious']}
    • Moderate:     {summary['moderate']}
    • Minor:        {summary['minor']}
  
  Passed Checks:    {summary['passed']}
  Warnings:         {summary['warnings']}
""")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='WCAG 2.1 Compliance Checker - Scan websites for accessibility issues',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://example.com
  %(prog)s https://example.com --max-pages 20
  %(prog)s https://example.com --format json --output results.json
  %(prog)s https://example.com --single-page
  %(prog)s https://spa-site.com --browser --max-pages 20
  %(prog)s https://spa-site.com --browser --wait-for "#main-content"

For more information, see README.md
        """
    )
    
    parser.add_argument('url', help='URL to scan')
    parser.add_argument('--max-pages', type=int, default=10,
                        help='Maximum number of pages to scan (default: 10)')
    parser.add_argument('--format', choices=['html', 'json', 'markdown'], default='html',
                        help='Report format (default: html)')
    parser.add_argument('--output', '-o', help='Output file name (auto-generated if not specified)')
    parser.add_argument('--single-page', action='store_true',
                        help='Only check the specified URL, do not crawl')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress progress output')
    parser.add_argument('--browser', action='store_true',
                        help='Use headless browser for JavaScript rendering')
    parser.add_argument('--wait-for', default='load',
                        help='Wait strategy: networkidle, load, domcontentloaded, or CSS selector (default: load)')

    args = parser.parse_args()
    
    if not args.quiet:
        print_banner()
    
    # Validate URL
    if not args.url.startswith(('http://', 'https://')):
        args.url = 'https://' + args.url
    
    # Create checker
    checker = WCAGChecker(
        use_browser=args.browser,
        wait_for=args.wait_for
    )

    if not args.quiet:
        print(f"  Target: {args.url}")
        print(f"  Max pages: {args.max_pages if not args.single_page else 1}")
        print(f"  Format: {args.format}")
        if args.browser:
            print(f"  Browser mode: Enabled (wait strategy: {args.wait_for})")
        print()
    
    try:
        if args.single_page:
            if not args.quiet:
                print_progress("Checking single page...")
            page_result = checker.check_page(args.url)
            
            # Wrap in site result for consistent reporting
            from checker import SiteResult
            result = SiteResult(
                base_url=args.url,
                timestamp=datetime.now().isoformat(),
                pages=[page_result]
            )
        else:
            if not args.quiet:
                print_progress("Starting site crawl...")
            result = checker.crawl_site(args.url, max_pages=args.max_pages)
        
        if not args.quiet:
            print_summary(result)
        
        # Generate report
        report = checker.generate_report(result, format=args.format)
        
        # Determine output filename
        if args.output:
            filename = args.output
        else:
            ext = {'html': 'html', 'json': 'json', 'markdown': 'md'}[args.format]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"wcag_report_{timestamp}.{ext}"
        
        # Save report
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n  ✅ Report saved: {filename}")
        print()
        
        # Return exit code based on issues found
        critical_issues = result.summary['critical']
        if critical_issues > 0:
            return 1
        return 0
        
    except Exception as e:
        print(f"\n  ❌ Error: {e}")
        if not args.quiet:
            import traceback
            traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
