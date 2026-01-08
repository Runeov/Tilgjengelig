"""
WCAG 2.1 Compliance Checker
Main module for crawling and checking websites for WCAG compliance.
Based on official Norwegian UU-tilsynet test rules.
https://www.uutilsynet.no/regelverk/oversikt-over-testregler-nettsteder/709
"""

import json
import re
import sys
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add the script directory to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from checkers.images import check_images
from checkers.headings import check_headings
from checkers.links import check_links
from checkers.forms import check_forms
from checkers.contrast import check_contrast
from checkers.keyboard import check_keyboard
from checkers.language import check_language
from checkers.structure import check_structure
from checkers.media import check_media
from checkers.aria import check_aria
from uu_test_rules import UU_TEST_RULES
from checkers.use_of_color import check_use_of_color
from checkers.name_role_value import check_name_role_value
from checkers.non_text_contrast import check_non_text_contrast

# Try to import accessibility statement checker (optional)
STATEMENT_CHECKER_AVAILABLE = False
try:
    from accessibility_statement import AccessibilityStatementChecker, AccessibilityStatementResult
    STATEMENT_CHECKER_AVAILABLE = True
except ImportError as e:
    print(f"Note: Accessibility statement checker not available: {e}")
    print("Continuing without statement checking...")
    AccessibilityStatementChecker = None
    AccessibilityStatementResult = None


@dataclass
class Issue:
    """Represents a single accessibility issue based on UU-tilsynet test rules."""
    rule_id: str  # UU test rule ID (e.g., "1.1.1a")
    criterion_id: str  # WCAG criterion (e.g., "1.1.1")
    criterion_name: str  # Norwegian name
    criterion_name_en: str  # English name
    level: str  # A, AA, AAA
    impact: str  # critical, serious, moderate, minor
    element: str
    selector: str
    issue: str
    fix: str
    context: str = ""


@dataclass
class PageResult:
    """Results for a single page."""
    url: str
    title: str
    timestamp: str
    issues: list = field(default_factory=list)
    passed: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    
    @property
    def summary(self):
        impact_counts = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
        for issue in self.issues:
            if issue.impact in impact_counts:
                impact_counts[issue.impact] += 1
        return {
            "total_issues": len(self.issues),
            "total_passed": len(self.passed),
            "total_warnings": len(self.warnings),
            **impact_counts
        }


@dataclass 
class SiteResult:
    """Results for entire site crawl."""
    base_url: str
    timestamp: str
    pages: list = field(default_factory=list)
    accessibility_statement: Optional[object] = None  # AccessibilityStatementResult when available
    
    @property
    def summary(self):
        total = {"issues": 0, "passed": 0, "warnings": 0, 
                 "critical": 0, "serious": 0, "moderate": 0, "minor": 0}
        for page in self.pages:
            s = page.summary
            total["issues"] += s["total_issues"]
            total["passed"] += s["total_passed"]
            total["warnings"] += s["total_warnings"]
            total["critical"] += s["critical"]
            total["serious"] += s["serious"]
            total["moderate"] += s["moderate"]
            total["minor"] += s["minor"]
        
        # Include accessibility statement info in summary
        statement_info = {}
        if self.accessibility_statement:
            stmt = self.accessibility_statement
            statement_info = {
                "has_accessibility_statement": stmt.has_statement_page,
                "statement_is_current": stmt.is_current,
                "statement_last_updated": stmt.last_updated,
                "statement_compliance": stmt.compliance_level
            }
        
        return {
            "pages_checked": len(self.pages),
            **total,
            **statement_info
        }


class WCAGChecker:
    """Main WCAG compliance checker class."""
    
    # File extensions to skip
    SKIP_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                       '.zip', '.rar', '.exe', '.dmg', '.mp3', '.mp4', '.avi', 
                       '.mov', '.wmv', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp'}
    
    def __init__(self, user_agent: str = None, exclude_patterns: list = None,
                 dedupe_articles: bool = True, article_patterns: list = None,
                 check_statement: bool = True):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent or "WCAGChecker/1.0 (Accessibility Compliance Tool)"
        })
        self.checked_urls = set()
        
        # URL patterns to exclude from crawling
        self.exclude_patterns = exclude_patterns or []
        
        # Deduplication for article/news pages
        self.dedupe_articles = dedupe_articles
        self.article_patterns = article_patterns or [
            '/aktuelt/', '/nyheter/', '/artikkel/', '/innhold/', '/news/', 
            '/article/', '/post/', '/blogg/', '/blog/'
        ]
        self.article_errors = {}  # Track deduplicated errors
        
        # Accessibility statement checker (only if available)
        self.check_statement = check_statement and STATEMENT_CHECKER_AVAILABLE
        self.statement_checker = None
        if self.check_statement and AccessibilityStatementChecker:
            self.statement_checker = AccessibilityStatementChecker(session=self.session)
        
        self.checkers = [
            ("Images", check_images),
            ("Headings", check_headings),
            ("Links", check_links),
            ("Forms", check_forms),
            ("Contrast", check_contrast),
            ("Keyboard", check_keyboard),
            ("Language", check_language),
            ("Structure", check_structure),
            ("Media", check_media),
            ("ARIA", check_aria),
            ("Use of Color", check_use_of_color),
("Name Role Value", check_name_role_value),
("Non-text Contrast", check_non_text_contrast),
        ]
    
    def check_accessibility_statement(self, url: str):
        """Check for accessibility statement on the website."""
        if not self.statement_checker:
            print("\n[!] Accessibility statement checker not available")
            return None
        
        try:
            print("\n" + "=" * 60)
            print("TILGJENGELIGHETSERKLARING SJEKK")
            print("=" * 60)
            
            result = self.statement_checker.check(url)
            
            # Print results
            if result.has_statement_page:
                print(f"[OK] Tilgjengelighetserklaring funnet: {result.statement_page_url}")
            else:
                print("[X] Ingen tilgjengelighetserklaring funnet pa nettstedet")
            
            if result.has_uustatus_link:
                print(f"[OK] Lenke til uustatus.no: {result.uustatus_url}")
                
                if result.uustatus_status:
                    status_icon = "[OK]" if result.uustatus_status == 'published' else "[!]"
                    print(f"   {status_icon} Status: {result.uustatus_status}")
                
                if result.last_updated:
                    current_icon = "[OK]" if result.is_current else "[!]"
                    print(f"   {current_icon} Sist oppdatert: {result.last_updated} ({result.days_since_update} dager siden)")
                
                if result.compliance_level:
                    level_labels = {
                        'full': '[OK] Fullt ut samsvar',
                        'partial': '[!] Delvis samsvar', 
                        'not_compliant': '[X] Ikke i samsvar'
                    }
                    print(f"   {level_labels.get(result.compliance_level, result.compliance_level)}")
            else:
                print("[!] Ingen lenke til uustatus.no funnet")
            
            if result.errors:
                print("\n[X] Feil:")
                for error in result.errors:
                    print(f"   - {error}")
            
            if result.warnings:
                print("\n[!] Advarsler:")
                for warning in result.warnings:
                    print(f"   - {warning}")
            
            print("=" * 60 + "\n")
            
            return result
            
        except Exception as e:
            print(f"\n[!] Error checking accessibility statement: {e}")
            print("Continuing without statement check...")
            print("=" * 60 + "\n")
            return None
    
    def should_skip_url(self, url: str) -> bool:
        """Check if URL should be skipped based on extension or pattern."""
        url_lower = url.lower()
        
        # Skip files by extension
        for ext in self.SKIP_EXTENSIONS:
            if url_lower.endswith(ext):
                return True
        
        # Skip excluded patterns
        for pattern in self.exclude_patterns:
            if pattern in url_lower:
                return True
        
        return False
    
    def is_article_page(self, url: str) -> bool:
        """Check if URL is an article/news page."""
        url_lower = url.lower()
        for pattern in self.article_patterns:
            if pattern in url_lower:
                return True
        return False
    
    def fetch_page(self, url: str, timeout: int = 30) -> Optional[tuple]:
        """Fetch a page and return (html, final_url) or None on error."""
        try:
            response = self.session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            return response.text, response.url
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML content."""
        return BeautifulSoup(html, 'html.parser')
    
    def extract_links(self, soup: BeautifulSoup, base_url: str) -> list:
        """Extract all internal links from a page."""
        links = []
        base_domain = urlparse(base_url).netloc
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            # Skip anchors, javascript, mailto, tel
            if href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
            
            # Convert relative to absolute
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            # Only include same domain
            if parsed.netloc == base_domain:
                # Remove fragments
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    clean_url += f"?{parsed.query}"
                
                # Skip PDFs and other files
                if not self.should_skip_url(clean_url):
                    links.append(clean_url)
        
        return list(set(links))
    
    def check_page(self, url: str, html: str = None) -> PageResult:
        """Run all WCAG checks on a single page."""
        if html is None:
            result = self.fetch_page(url)
            if result is None:
                return PageResult(
                    url=url,
                    title="Error: Could not fetch page",
                    timestamp=datetime.now().isoformat(),
                    issues=[Issue(
                        criterion_id="N/A",
                        criterion_name="Page Fetch",
                        level="A",
                        impact="critical",
                        element="page",
                        selector="",
                        issue=f"Could not fetch page: {url}",
                        fix="Ensure the URL is correct and the server is responding"
                    )]
                )
            html, url = result
        
        soup = self.parse_html(html)
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else "No title"
        
        page_result = PageResult(
            url=url,
            title=title,
            timestamp=datetime.now().isoformat()
        )
        
        # Run all checkers
        for checker_name, checker_func in self.checkers:
            try:
                issues, passed, warnings = checker_func(soup, url, html)
                page_result.issues.extend(issues)
                page_result.passed.extend(passed)
                page_result.warnings.extend(warnings)
            except Exception as e:
                print(f"Error in {checker_name} checker: {e}")
        
        return page_result
    
    def crawl_site(self, start_url: str, max_pages: int = 50, 
                   max_workers: int = 5) -> SiteResult:
        """Crawl a site and check multiple pages."""
        
        # First, check for accessibility statement
        statement_result = None
        if self.check_statement and self.statement_checker:
            statement_result = self.check_accessibility_statement(start_url)
            
            # If statement check succeeded, show warnings if needed
            if statement_result:
                if statement_result.has_statement_page and not statement_result.is_current:
                    if statement_result.last_updated:
                        print(f"[!] ADVARSEL: Tilgjengelighetserklaringen er utdatert ({statement_result.days_since_update} dager gammel)")
                        print("   Anbefaling: Oppdater erklaringen for WCAG-sjekk kjores")
                elif not statement_result.has_statement_page:
                    print("[!] ADVARSEL: Nettstedet mangler tilgjengelighetserklaring")
                    print("   Dette er et lovkrav for offentlige nettsteder")
        
        site_result = SiteResult(
            base_url=start_url,
            timestamp=datetime.now().isoformat(),
            accessibility_statement=statement_result
        )
        
        urls_to_check = [start_url]
        self.checked_urls = set()
        self.article_errors = {}  # Reset article error tracking
        article_pages_checked = 0
        
        while urls_to_check and len(self.checked_urls) < max_pages:
            current_batch = urls_to_check[:max_workers]
            urls_to_check = urls_to_check[max_workers:]
            
            for url in current_batch:
                if url in self.checked_urls:
                    continue
                
                # Skip excluded URLs
                if self.should_skip_url(url):
                    continue
                    
                self.checked_urls.add(url)
                is_article = self.is_article_page(url)
                
                if is_article:
                    article_pages_checked += 1
                    print(f"Checking (article): {url}")
                else:
                    print(f"Checking: {url}")
                
                result = self.fetch_page(url)
                if result is None:
                    continue
                
                html, final_url = result
                soup = self.parse_html(html)
                
                # Check this page
                page_result = self.check_page(final_url, html)
                
                # Handle article deduplication
                if is_article and self.dedupe_articles:
                    for issue in page_result.issues:
                        # Create a key based on criterion and issue type
                        key = f"{issue.criterion_id}|{issue.issue}"
                        if key not in self.article_errors:
                            self.article_errors[key] = {
                                'issue': issue,
                                'count': 0,
                                'example_urls': []
                            }
                        self.article_errors[key]['count'] += 1
                        if len(self.article_errors[key]['example_urls']) < 3:
                            self.article_errors[key]['example_urls'].append(final_url)
                    
                    # Don't add individual article page results
                    # We'll add a summary at the end
                else:
                    site_result.pages.append(page_result)
                
                # Extract more links
                new_links = self.extract_links(soup, final_url)
                for link in new_links:
                    if link not in self.checked_urls and link not in urls_to_check:
                        urls_to_check.append(link)
        
        # Add article summary page if we have deduplicated errors
        if self.article_errors and article_pages_checked > 0:
            article_summary = PageResult(
                url=f"[ARTICLE PAGES SUMMARY - {article_pages_checked} pages]",
                title=f"Recurring Issues in Article/News Pages ({article_pages_checked} pages scanned)",
                timestamp=datetime.now().isoformat()
            )
            
            for key, data in self.article_errors.items():
                issue = data['issue']
                # Modify the issue to show count
                summary_issue = type('Issue', (), {
                    'criterion_id': issue.criterion_id,
                    'criterion_name': issue.criterion_name,
                    'level': issue.level,
                    'impact': issue.impact,
                    'element': issue.element,
                    'selector': issue.selector,
                    'issue': f"{issue.issue} (×{data['count']} across article pages)",
                    'fix': issue.fix,
                    'context': f"Example pages: {', '.join(data['example_urls'])}"
                })()
                article_summary.issues.append(summary_issue)
            
            site_result.pages.append(article_summary)
            print(f"\n📰 Deduplicated {sum(d['count'] for d in self.article_errors.values())} article errors into {len(self.article_errors)} unique types")
        
        return site_result
    
    def generate_report(self, result: SiteResult, format: str = "json") -> str:
        """Generate a report from the results."""
        if format == "json":
            return self._generate_json_report(result)
        elif format == "html":
            return self._generate_html_report(result)
        elif format == "markdown":
            return self._generate_markdown_report(result)
        else:
            raise ValueError(f"Unknown format: {format}")
    
    def _generate_json_report(self, result: SiteResult) -> str:
        """Generate JSON report."""
        def convert(obj):
            if hasattr(obj, '__dataclass_fields__'):
                d = asdict(obj)
                if hasattr(obj, 'summary'):
                    d['summary'] = obj.summary
                return d
            return obj
        
        output = {
            "base_url": result.base_url,
            "timestamp": result.timestamp,
            "summary": result.summary,
            "pages": [convert(p) for p in result.pages]
        }
        
        # Include accessibility statement if available
        if result.accessibility_statement:
            output["accessibility_statement"] = result.accessibility_statement.summary
        
        return json.dumps(output, indent=2, default=str)
    
    def _generate_statement_html(self, result: SiteResult) -> str:
        """Generate HTML section for accessibility statement status."""
        stmt = result.accessibility_statement
        
        if stmt is None:
            return ""
        
        html = """
    <div class="statement-section">
        <h2>📋 Tilgjengelighetserklæring Status</h2>
        <div class="statement-status">
"""
        
        # Statement page status
        if stmt.has_statement_page:
            html += f'''
            <div class="statement-item success">
                ✅ <strong>Tilgjengelighetserklæring funnet</strong>
            </div>'''
            if stmt.statement_page_url:
                html += f'''
            <div class="statement-item">
                🔗 <a href="{stmt.statement_page_url}" class="statement-link" target="_blank">Gå til erklæring</a>
            </div>'''
        else:
            html += '''
            <div class="statement-item error">
                ❌ <strong>Ingen tilgjengelighetserklæring funnet</strong>
            </div>'''
        
        # uustatus.no status
        if stmt.has_uustatus_link:
            html += f'''
            <div class="statement-item success">
                ✅ <strong>Registrert på uustatus.no</strong>
            </div>'''
            if stmt.uustatus_url:
                html += f'''
            <div class="statement-item">
                🔗 <a href="{stmt.uustatus_url}" class="statement-link" target="_blank">Se på uustatus.no</a>
            </div>'''
        else:
            html += '''
            <div class="statement-item warning">
                ⚠️ <strong>Mangler lenke til uustatus.no</strong>
            </div>'''
        
        # Update status
        if stmt.last_updated:
            if stmt.is_current:
                html += f'''
            <div class="statement-item success">
                ✅ <strong>Oppdatert:</strong> {stmt.last_updated} ({stmt.days_since_update} dager siden)
            </div>'''
            else:
                html += f'''
            <div class="statement-item warning">
                ⚠️ <strong>Utdatert:</strong> {stmt.last_updated} ({stmt.days_since_update} dager siden)
            </div>'''
        
        # Compliance level
        if stmt.compliance_level:
            compliance_info = {
                'full': ('success', '✅ Fullt ut samsvar med kravene'),
                'partial': ('warning', '⚠️ Delvis samsvar med kravene'),
                'not_compliant': ('error', '❌ Ikke i samsvar med kravene')
            }
            class_name, text = compliance_info.get(stmt.compliance_level, ('', stmt.compliance_level))
            html += f'''
            <div class="statement-item {class_name}">
                {text}
            </div>'''
        
        html += """
        </div>"""
        
        # Details section
        if stmt.organization_name or stmt.errors or stmt.warnings:
            html += """
        <div class="statement-details">"""
            
            if stmt.organization_name:
                html += f'''
            <p><strong>Organisasjon:</strong> {stmt.organization_name}</p>'''
            
            if stmt.errors:
                html += '<p style="color:#c00;"><strong>Feil:</strong></p><ul style="color:#c00;">'
                for error in stmt.errors:
                    html += f'<li>{error}</li>'
                html += '</ul>'
            
            if stmt.warnings:
                html += '<p style="color:#e65100;"><strong>Advarsler:</strong></p><ul style="color:#e65100;">'
                for warning in stmt.warnings:
                    html += f'<li>{warning}</li>'
                html += '</ul>'
            
            html += """
        </div>"""
        
        html += """
    </div>
"""
        
        return html
    
    def _generate_html_report(self, result: SiteResult) -> str:
        """Generate HTML report based on UU-tilsynet format."""
        summary = result.summary
        
        html = f"""<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WCAG 2.1 Tilgjengelighetsrapport - {result.base_url}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               line-height: 1.6; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        h1, h2, h3 {{ color: #1a1a2e; }}
        .header {{ background: #003366; color: white; padding: 30px; border-radius: 8px; margin-bottom: 20px; }}
        .header h1 {{ margin: 0; color: white; }}
        .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
        .statement-section {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .statement-section h2 {{ margin-top: 0; color: #003366; }}
        .statement-status {{ display: flex; flex-wrap: wrap; gap: 15px; margin-top: 15px; }}
        .statement-item {{ display: flex; align-items: center; gap: 8px; padding: 10px 15px; border-radius: 6px; }}
        .statement-item.success {{ background: #e8f5e9; color: #2e7d32; }}
        .statement-item.warning {{ background: #fff3e0; color: #e65100; }}
        .statement-item.error {{ background: #fee; color: #c00; }}
        .statement-link {{ color: #003366; text-decoration: none; }}
        .statement-link:hover {{ text-decoration: underline; }}
        .statement-details {{ margin-top: 15px; padding: 15px; background: #f8f9fa; border-radius: 6px; }}
        .statement-details p {{ margin: 5px 0; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); 
                   gap: 15px; margin: 20px 0; }}
        .stat {{ background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-value {{ font-size: 2em; font-weight: bold; }}
        .stat-label {{ color: #666; }}
        .critical {{ background: #fee; color: #c00; }}
        .serious {{ background: #fff3e0; color: #e65100; }}
        .moderate {{ background: #fff8e1; color: #f9a825; }}
        .minor {{ background: #e8f5e9; color: #2e7d32; }}
        .passed {{ background: #e8f5e9; }}
        .page {{ background: white; border-radius: 8px; margin: 20px 0; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .page-header {{ background: #f8f9fa; padding: 15px 20px; border-bottom: 1px solid #ddd; }}
        .page-header h3 {{ margin: 0; }}
        .page-url {{ color: #666; font-size: 0.9em; word-break: break-all; }}
        .issues {{ padding: 20px; }}
        .issue {{ background: #fff; border-left: 4px solid #ccc; padding: 15px; margin: 10px 0; border-radius: 0 4px 4px 0; }}
        .issue.critical {{ border-color: #c00; background: #fff5f5; }}
        .issue.serious {{ border-color: #e65100; background: #fff8f0; }}
        .issue.moderate {{ border-color: #f9a825; background: #fffdf0; }}
        .issue.minor {{ border-color: #2e7d32; background: #f5fff5; }}
        .issue-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 10px; }}
        .rule-id {{ font-weight: bold; font-size: 1.1em; color: #003366; }}
        .criterion {{ color: #666; font-size: 0.9em; }}
        .impact {{ padding: 4px 12px; border-radius: 4px; font-size: 0.85em; font-weight: 500; }}
        .impact.critical {{ background: #c00; color: white; }}
        .impact.serious {{ background: #e65100; color: white; }}
        .impact.moderate {{ background: #f9a825; color: #333; }}
        .impact.minor {{ background: #2e7d32; color: white; }}
        .element {{ background: #f5f5f5; padding: 10px; font-family: monospace; 
                   font-size: 0.9em; overflow-x: auto; margin: 10px 0; border-radius: 4px; }}
        .fix {{ background: #e3f2fd; padding: 12px; border-radius: 4px; margin-top: 10px; }}
        .fix::before {{ content: "💡 Løsning: "; font-weight: bold; }}
        .no-issues {{ color: #2e7d32; padding: 20px; text-align: center; font-size: 1.1em; }}
        details {{ margin: 10px 0; }}
        summary {{ cursor: pointer; padding: 12px 15px; background: #f5f5f5; border-radius: 4px; font-weight: 500; }}
        summary:hover {{ background: #eee; }}
        .legend {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .legend h3 {{ margin-top: 0; }}
        .legend-items {{ display: flex; gap: 20px; flex-wrap: wrap; }}
        .legend-item {{ display: flex; align-items: center; gap: 8px; }}
        .legend-color {{ width: 16px; height: 16px; border-radius: 3px; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 0.9em; }}
        .footer a {{ color: #003366; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>WCAG 2.1 Tilgjengelighetsrapport</h1>
        <p>Basert på testregler fra Tilsynet for universell utforming av IKT</p>
        <p><strong>Nettsted:</strong> {result.base_url}</p>
        <p><strong>Dato:</strong> {result.timestamp}</p>
    </div>
    
    {self._generate_statement_html(result)}
    
    <div class="legend">
        <h3>Alvorlighetsgrad</h3>
        <div class="legend-items">
            <div class="legend-item"><div class="legend-color" style="background:#c00"></div> Kritisk - Blokkerer tilgang</div>
            <div class="legend-item"><div class="legend-color" style="background:#e65100"></div> Alvorlig - Store barrierer</div>
            <div class="legend-item"><div class="legend-color" style="background:#f9a825"></div> Moderat - Betydelige problemer</div>
            <div class="legend-item"><div class="legend-color" style="background:#2e7d32"></div> Mindre - Bør forbedres</div>
        </div>
    </div>
    
    <h2>Sammendrag</h2>
    <div class="summary">
        <div class="stat">
            <div class="stat-value">{summary['pages_checked']}</div>
            <div class="stat-label">Sider testet</div>
        </div>
        <div class="stat">
            <div class="stat-value">{summary['issues']}</div>
            <div class="stat-label">Totalt avvik</div>
        </div>
        <div class="stat critical">
            <div class="stat-value">{summary['critical']}</div>
            <div class="stat-label">Kritiske</div>
        </div>
        <div class="stat serious">
            <div class="stat-value">{summary['serious']}</div>
            <div class="stat-label">Alvorlige</div>
        </div>
        <div class="stat moderate">
            <div class="stat-value">{summary['moderate']}</div>
            <div class="stat-label">Moderate</div>
        </div>
        <div class="stat minor">
            <div class="stat-value">{summary['minor']}</div>
            <div class="stat-label">Mindre</div>
        </div>
        <div class="stat passed">
            <div class="stat-value">{summary['passed']}</div>
            <div class="stat-label">Bestått</div>
        </div>
    </div>
    
    <h2>Resultater per side</h2>
"""
        
        for page in result.pages:
            page_summary = page.summary
            html += f"""
    <div class="page">
        <div class="page-header">
            <h3>{page.title}</h3>
            <div class="page-url">{page.url}</div>
            <div>Avvik: {page_summary['total_issues']} | Bestått: {page_summary['total_passed']}</div>
        </div>
        <div class="issues">
"""
            if not page.issues:
                html += '<div class="no-issues">✅ Ingen avvik funnet på denne siden!</div>'
            else:
                # Group by criterion
                by_criterion = {}
                for issue in page.issues:
                    key = f"{issue.criterion_id} {issue.criterion_name}"
                    if key not in by_criterion:
                        by_criterion[key] = []
                    by_criterion[key].append(issue)
                
                for criterion, issues in by_criterion.items():
                    html += f'<details><summary>{criterion} ({len(issues)} avvik)</summary>'
                    for issue in issues:
                        element_escaped = issue.element.replace('<', '&lt;').replace('>', '&gt;')
                        rule_id = getattr(issue, 'rule_id', issue.criterion_id)
                        html += f"""
            <div class="issue {issue.impact}">
                <div class="issue-header">
                    <div>
                        <span class="rule-id">Testregel {rule_id}</span>
                        <span class="criterion">({issue.criterion_id} - Nivå {issue.level})</span>
                    </div>
                    <span class="impact {issue.impact}">{issue.impact.upper()}</span>
                </div>
                <p>{issue.issue}</p>
                <div class="element">{element_escaped}</div>
                <div class="fix">{issue.fix}</div>
            </div>
"""
                    html += '</details>'
            
            html += """
        </div>
    </div>
"""
        
        html += """
    <div class="footer">
        <p>Testreglene er basert på <a href="https://www.uutilsynet.no/regelverk/oversikt-over-testregler-nettsteder/709" target="_blank">UU-tilsynets offisielle testregler</a></p>
    </div>
</body>
</html>
"""
        return html
    
    def _generate_markdown_report(self, result: SiteResult) -> str:
        """Generate Markdown report."""
        summary = result.summary
        
        md = f"""# WCAG 2.1 Compliance Report

**Site:** {result.base_url}  
**Date:** {result.timestamp}

## Summary

| Metric | Count |
|--------|-------|
| Pages Checked | {summary['pages_checked']} |
| Total Issues | {summary['issues']} |
| Critical | {summary['critical']} |
| Serious | {summary['serious']} |
| Moderate | {summary['moderate']} |
| Minor | {summary['minor']} |
| Passed Checks | {summary['passed']} |

## Page Results

"""
        
        for page in result.pages:
            md += f"### {page.title}\n\n"
            md += f"**URL:** {page.url}\n\n"
            
            if not page.issues:
                md += "✅ No issues found on this page!\n\n"
            else:
                for issue in page.issues:
                    md += f"#### ❌ {issue.criterion_id} {issue.criterion_name}\n\n"
                    md += f"- **Impact:** {issue.impact.upper()}\n"
                    md += f"- **Level:** {issue.level}\n"
                    md += f"- **Issue:** {issue.issue}\n"
                    md += f"- **Element:** `{issue.element[:100]}...`\n" if len(issue.element) > 100 else f"- **Element:** `{issue.element}`\n"
                    md += f"- **Fix:** {issue.fix}\n\n"
            
            md += "---\n\n"
        
        return md


def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python checker.py <url> [options]")
        print("")
        print("Options:")
        print("  --max-pages N       Maximum pages to crawl (default: 10)")
        print("  --format FORMAT     Output format: json, html, markdown (default: html)")
        print("  --exclude PATTERNS  Comma-separated URL patterns to skip")
        print("  --no-dedupe         Don't deduplicate article/news errors")
        print("  --no-statement      Skip accessibility statement check")
        print("  --article-patterns  Comma-separated patterns that identify article pages")
        print("  --output FILE       Output file name")
        print("")
        print("Example:")
        print("  python checker.py https://example.com --max-pages 100 --format html")
        print("  python checker.py https://example.com --exclude '/old/,/archive/'")
        print("  python checker.py https://example.com --no-statement")
        sys.exit(1)
    
    url = sys.argv[1]
    max_pages = 10
    output_format = "html"
    exclude_patterns = []
    dedupe_articles = True
    article_patterns = None
    check_statement = True
    output_file = None
    
    # Parse arguments
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--max-pages" and i + 1 < len(args):
            max_pages = int(args[i + 1])
            i += 2
        elif args[i] == "--format" and i + 1 < len(args):
            output_format = args[i + 1]
            i += 2
        elif args[i] == "--exclude" and i + 1 < len(args):
            exclude_patterns = [p.strip() for p in args[i + 1].split(',')]
            i += 2
        elif args[i] == "--no-dedupe":
            dedupe_articles = False
            i += 1
        elif args[i] == "--no-statement":
            check_statement = False
            i += 1
        elif args[i] == "--article-patterns" and i + 1 < len(args):
            article_patterns = [p.strip() for p in args[i + 1].split(',')]
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        else:
            i += 1
    
    checker = WCAGChecker(
        exclude_patterns=exclude_patterns,
        dedupe_articles=dedupe_articles,
        article_patterns=article_patterns,
        check_statement=check_statement
    )
    
    print(f"Starting WCAG check for: {url}")
    print(f"Max pages: {max_pages}")
    print(f"Check accessibility statement: {'Yes' if check_statement else 'No'}")
    print(f"Skipping: PDFs and file downloads")
    if exclude_patterns:
        print(f"Excluding patterns: {exclude_patterns}")
    if dedupe_articles:
        print(f"Deduplicating article/news errors: Yes")
    print("-" * 50)
    
    result = checker.crawl_site(url, max_pages=max_pages)
    
    print("-" * 50)
    print(f"Checked {len(result.pages)} pages")
    print(f"Found {result.summary['issues']} issues")
    print(f"  🔴 Critical: {result.summary['critical']}")
    print(f"  🟠 Serious: {result.summary['serious']}")
    print(f"  🟡 Moderate: {result.summary['moderate']}")
    print(f"  🟢 Minor: {result.summary['minor']}")
    
    report = checker.generate_report(result, format=output_format)
    
    # Save report
    if output_file:
        filename = output_file
    else:
        ext = {"json": "json", "html": "html", "markdown": "md"}[output_format]
        filename = f"wcag_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\nReport saved to: {filename}")


if __name__ == "__main__":
    main()
