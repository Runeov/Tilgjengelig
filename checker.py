"""
WCAG 2.1 Compliance Checker
Main module for crawling and checking websites for WCAG compliance.
Based on official Norwegian UU-tilsynet test rules.
https://www.uutilsynet.no/regelverk/oversikt-over-testregler-nettsteder/709
"""

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

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


@dataclass
class AccessibilityStatementResult:
    """Result of accessibility statement check."""
    has_statement_page: bool = False
    statement_page_url: str = None
    uustatus_url: str = None
    is_current: bool = False
    last_updated: str = None
    compliance_status: str = None
    organization_name: str = None



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
    accessibility_statement: any = None  # Statement check results
    
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
        return {
            "pages_checked": len(self.pages),
            **total
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
        
        # Whether to check for accessibility statement
        self.check_statement = check_statement
        
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
        ]
    
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
    
    def check_accessibility_statement(self, base_url: str) -> AccessibilityStatementResult:
        """Check for accessibility statement on the site."""
        result = AccessibilityStatementResult()
        
        # Common URLs for accessibility statements
        statement_paths = [
            '/tilgjengelighetserklaering',
            '/tilgjengelighetserklaring', 
            '/universell-utforming',
            '/accessibility',
            '/tilgjengelighet',
        ]
        
        parsed = urlparse(base_url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"
        
        # First, try to find statement link on homepage
        try:
            resp = self.session.get(base_url, timeout=20)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Look for links to statement
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '').lower()
                    text = link.get_text().lower()
                    
                    if any(term in href or term in text for term in 
                           ['tilgjengelighet', 'accessibility', 'universell']):
                        full_url = urljoin(base_url, link['href'])
                        result.statement_page_url = full_url
                        result.has_statement_page = True
                        break
        except Exception:
            pass
        
        # Try common paths if not found
        if not result.has_statement_page:
            for path in statement_paths:
                try:
                    test_url = base_domain + path
                    resp = self.session.head(test_url, timeout=10, allow_redirects=True)
                    if resp.status_code == 200:
                        result.statement_page_url = test_url
                        result.has_statement_page = True
                        break
                except Exception:
                    continue
        
        # Check uustatus.no for registration
        try:
            domain = parsed.netloc.replace('www.', '')
            uustatus_api = f"https://uustatus.no/api/declarations?url={domain}"
            resp = self.session.get(uustatus_api, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    declaration = data[0]
                    result.uustatus_url = f"https://uustatus.no/nb/erklaringer/publisert/{declaration.get('id', '')}"
                    result.has_statement_page = True
                    result.organization_name = declaration.get('name', '')
                    result.compliance_status = declaration.get('status', '')
                    
                    # Check if current (within last year)
                    updated = declaration.get('updated')
                    if updated:
                        result.last_updated = updated
                        try:
                            updated_date = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                            age_days = (datetime.now(updated_date.tzinfo) - updated_date).days
                            result.is_current = age_days < 365
                        except Exception:
                            result.is_current = False
        except Exception:
            pass
        
        return result
    
    def crawl_site(self, start_url: str, max_pages: int = 50, 
                   max_workers: int = 5) -> SiteResult:
        """Crawl a site and check multiple pages."""
        site_result = SiteResult(
            base_url=start_url,
            timestamp=datetime.now().isoformat()
        )
        
        # Check accessibility statement if enabled
        if self.check_statement:
            print("Checking accessibility statement...")
            site_result.accessibility_statement = self.check_accessibility_statement(start_url)
            if site_result.accessibility_statement.has_statement_page:
                print(f"  ✓ Statement found: {site_result.accessibility_statement.statement_page_url or site_result.accessibility_statement.uustatus_url}")
            else:
                print("  ✗ No statement found")
        
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
        return json.dumps(output, indent=2, default=str)
    
    def _generate_html_report(self, result: SiteResult) -> str:
        """Generate HTML report based on UU-tilsynet format with interactive features."""
        summary = result.summary
        
        # Enhanced CSS with interactive features
        css = """
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               line-height: 1.6; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        h1, h2, h3 { color: #1a1a2e; }
        .header { background: #003366; color: white; padding: 30px; border-radius: 8px; margin-bottom: 20px; }
        .header h1 { margin: 0; color: white; }
        .header p { margin: 10px 0 0 0; opacity: 0.9; }
        .statement-section { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .statement-section h2 { margin-top: 0; color: #003366; }
        .statement-status { display: flex; flex-wrap: wrap; gap: 15px; margin-top: 15px; }
        .statement-item { display: flex; align-items: center; gap: 8px; padding: 10px 15px; border-radius: 6px; }
        .statement-item.success { background: #e8f5e9; color: #2e7d32; }
        .statement-item.warning { background: #fff3e0; color: #e65100; }
        .statement-item.error { background: #fee; color: #c00; }
        .statement-link { color: #003366; text-decoration: none; }
        .statement-link:hover { text-decoration: underline; }
        .statement-details { margin-top: 15px; padding: 15px; background: #f8f9fa; border-radius: 6px; }
        .statement-details p { margin: 5px 0; }
        
        /* Enhanced Summary Stats */
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 12px;
            margin: 20px 0;
        }
        .stat {
            background: white;
            padding: 15px 10px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.2s;
            position: relative;
        }
        .stat-value { font-size: 1.8em; font-weight: bold; }
        .stat-label { color: #666; font-size: 0.85em; }
        
        .stat.filterable {
            cursor: pointer;
            border: 3px solid transparent;
            user-select: none;
        }
        .stat.filterable:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .stat.filterable.active { border-color: currentColor; }
        .stat.filterable::before {
            content: '✓';
            position: absolute;
            top: 6px;
            right: 8px;
            font-size: 12px;
            font-weight: bold;
            opacity: 0;
            transition: opacity 0.2s;
        }
        .stat.filterable.active::before { opacity: 1; }
        .stat.filterable:not(.active) { opacity: 0.4; filter: grayscale(50%); }
        .stat.filterable:not(.active):hover { opacity: 0.7; }
        
        .stat.critical { background: #fee; color: #c00; }
        .stat.critical.active { border-color: #c00; }
        .stat.serious { background: #fff3e0; color: #e65100; }
        .stat.serious.active { border-color: #e65100; }
        .stat.moderate { background: #fff8e1; color: #9e6b00; }
        .stat.moderate.active { border-color: #f9a825; }
        .stat.minor { background: #e8f5e9; color: #2e7d32; }
        .stat.minor.active { border-color: #2e7d32; }
        .stat.passed { background: #e8f5e9; color: #2e7d32; }
        
        .stat.pages-control {
            background: linear-gradient(135deg, #003366 0%, #004080 100%);
            color: white;
            cursor: pointer;
        }
        .stat.pages-control:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,51,102,0.3);
        }
        .stat.pages-control .stat-value {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }
        .pages-adjust { display: flex; flex-direction: column; gap: 1px; }
        .pages-adjust button {
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            width: 22px;
            height: 16px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 9px;
            line-height: 1;
            transition: background 0.2s;
        }
        .pages-adjust button:hover { background: rgba(255,255,255,0.4); }
        .stat.pages-control .stat-label { color: rgba(255,255,255,0.9); }
        
        .stat.rescan-btn { background: #2e7d32; color: white; cursor: pointer; }
        .stat.rescan-btn:hover {
            background: #1b5e20;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(46,125,50,0.3);
        }
        .stat.rescan-btn .stat-value { font-size: 1.5em; }
        .stat.rescan-btn .stat-label { color: rgba(255,255,255,0.9); }
        
        .filter-status {
            background: #f8f9fa;
            padding: 12px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }
        .filter-status-text { font-size: 14px; color: #666; }
        .filter-status-text strong { color: #333; font-size: 1.1em; }
        .filter-actions { display: flex; gap: 8px; flex-wrap: wrap; }
        .filter-action-btn {
            padding: 6px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }
        .filter-action-btn:hover { background: #e9e9e9; border-color: #999; }
        
        .issue.hidden { display: none !important; }
        details.hidden { display: none !important; }
        
        .page { background: white; border-radius: 8px; margin: 20px 0; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .page-header { background: #f8f9fa; padding: 15px 20px; border-bottom: 1px solid #ddd; }
        .page-header h3 { margin: 0; }
        .page-url { color: #666; font-size: 0.9em; word-break: break-all; }
        .issues { padding: 20px; }
        .issue { background: #fff; border-left: 4px solid #ccc; padding: 15px; margin: 10px 0; border-radius: 0 4px 4px 0; }
        .issue.critical { border-color: #c00; background: #fff5f5; }
        .issue.serious { border-color: #e65100; background: #fff8f0; }
        .issue.moderate { border-color: #f9a825; background: #fffdf0; }
        .issue.minor { border-color: #2e7d32; background: #f5fff5; }
        .issue-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 10px; }
        .rule-id { font-weight: bold; font-size: 1.1em; color: #003366; }
        .criterion { color: #666; font-size: 0.9em; }
        .impact { padding: 4px 12px; border-radius: 4px; font-size: 0.85em; font-weight: 500; }
        .impact.critical { background: #c00; color: white; }
        .impact.serious { background: #e65100; color: white; }
        .impact.moderate { background: #f9a825; color: #333; }
        .impact.minor { background: #2e7d32; color: white; }
        .element { background: #f5f5f5; padding: 10px; font-family: monospace; 
                   font-size: 0.9em; overflow-x: auto; margin: 10px 0; border-radius: 4px; }
        .fix { background: #e3f2fd; padding: 12px; border-radius: 4px; margin-top: 10px; }
        .fix::before { content: "💡 Løsning: "; font-weight: bold; }
        .no-issues { color: #2e7d32; padding: 20px; text-align: center; font-size: 1.1em; }
        details { margin: 10px 0; }
        summary { cursor: pointer; padding: 12px 15px; background: #f5f5f5; border-radius: 4px; font-weight: 500; }
        summary:hover { background: #eee; }
        .legend { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .legend h3 { margin-top: 0; }
        .legend-items { display: flex; gap: 20px; flex-wrap: wrap; }
        .legend-item { display: flex; align-items: center; gap: 8px; }
        .legend-color { width: 16px; height: 16px; border-radius: 3px; }
        .footer { text-align: center; padding: 20px; color: #666; font-size: 0.9em; }
        .footer a { color: #003366; }
        
        /* Modal */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.6);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            backdrop-filter: blur(2px);
        }
        .modal-overlay.active { display: flex; }
        .modal {
            background: white;
            padding: 30px;
            border-radius: 12px;
            max-width: 520px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .modal h3 { margin: 0 0 20px 0; color: #003366; font-size: 1.4em; }
        .modal-url {
            background: #f5f5f5;
            padding: 12px 15px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 13px;
            word-break: break-all;
            border-left: 4px solid #003366;
        }
        .modal-pages {
            display: flex;
            align-items: center;
            gap: 15px;
            margin: 25px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .modal-pages label { font-weight: 600; color: #333; }
        .modal-pages input {
            width: 80px;
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 18px;
            font-weight: bold;
            text-align: center;
        }
        .modal-pages input:focus { border-color: #003366; outline: none; }
        .modal-pages-hint { font-size: 12px; color: #888; }
        .modal-command {
            background: #1a1a2e;
            color: #4ade80;
            padding: 15px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 13px;
            margin: 20px 0;
            overflow-x: auto;
        }
        .modal-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 25px; }
        .modal-btn {
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s;
        }
        .modal-btn.secondary { background: #f5f5f5; color: #333; }
        .modal-btn.secondary:hover { background: #e0e0e0; }
        .modal-btn.primary { background: #003366; color: white; }
        .modal-btn.primary:hover { background: #004488; }
        """
        
        html = f"""<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WCAG 2.1 Tilgjengelighetsrapport - {result.base_url}</title>
    <style>{css}</style>
    <script>
        var BASE_URL = "{result.base_url}";
        var TOTAL_ISSUES = {summary['issues']};
        var maxPages = {summary['pages_checked']};
        var activeFilters = {{ critical: true, serious: true, moderate: true, minor: true }};
        
        function toggleFilter(severity) {{
            activeFilters[severity] = !activeFilters[severity];
            var stat = document.querySelector('.stat[data-severity="' + severity + '"]');
            if (stat) {{
                if (activeFilters[severity]) {{ stat.classList.add('active'); }}
                else {{ stat.classList.remove('active'); }}
            }}
            applyFilters();
        }}
        
        function selectAll() {{
            var keys = ['critical', 'serious', 'moderate', 'minor'];
            for (var i = 0; i < keys.length; i++) {{
                activeFilters[keys[i]] = true;
                var stat = document.querySelector('.stat[data-severity="' + keys[i] + '"]');
                if (stat) stat.classList.add('active');
            }}
            applyFilters();
        }}
        
        function selectNone() {{
            var keys = ['critical', 'serious', 'moderate', 'minor'];
            for (var i = 0; i < keys.length; i++) {{
                activeFilters[keys[i]] = false;
                var stat = document.querySelector('.stat[data-severity="' + keys[i] + '"]');
                if (stat) stat.classList.remove('active');
            }}
            applyFilters();
        }}
        
        function applyFilters() {{
            var visibleCount = 0;
            var issues = document.querySelectorAll('.issue[data-severity]');
            for (var i = 0; i < issues.length; i++) {{
                var issue = issues[i];
                var severity = issue.getAttribute('data-severity');
                if (activeFilters[severity]) {{
                    issue.classList.remove('hidden');
                    visibleCount++;
                }} else {{
                    issue.classList.add('hidden');
                }}
            }}
            var details = document.querySelectorAll('details');
            for (var i = 0; i < details.length; i++) {{
                var detail = details[i];
                var childIssues = detail.querySelectorAll('.issue[data-severity]');
                var hasVisible = false;
                for (var j = 0; j < childIssues.length; j++) {{
                    if (!childIssues[j].classList.contains('hidden')) {{ hasVisible = true; break; }}
                }}
                if (hasVisible) {{ detail.classList.remove('hidden'); }}
                else {{ detail.classList.add('hidden'); }}
            }}
            var countEl = document.getElementById('visibleCount');
            var totalEl = document.getElementById('visibleTotal');
            if (countEl) countEl.textContent = visibleCount;
            if (totalEl) totalEl.textContent = visibleCount;
        }}
        
        function expandAll() {{
            var details = document.querySelectorAll('details:not(.hidden)');
            for (var i = 0; i < details.length; i++) {{ details[i].open = true; }}
        }}
        
        function collapseAll() {{
            var details = document.querySelectorAll('details');
            for (var i = 0; i < details.length; i++) {{ details[i].open = false; }}
        }}
        
        function adjustPages(delta) {{
            maxPages = Math.max(1, Math.min(500, maxPages + delta));
            var pagesEl = document.getElementById('pagesValue');
            var inputEl = document.getElementById('maxPages');
            if (pagesEl) pagesEl.textContent = maxPages;
            if (inputEl) inputEl.value = maxPages;
            updateCommand();
        }}
        
        function showRescanModal() {{
            var modal = document.getElementById('rescanModal');
            var inputEl = document.getElementById('maxPages');
            if (modal) modal.classList.add('active');
            if (inputEl) inputEl.value = maxPages;
            updateCommand();
        }}
        
        function closeRescanModal() {{
            var modal = document.getElementById('rescanModal');
            if (modal) modal.classList.remove('active');
        }}
        
        function updateCommand() {{
            var inputEl = document.getElementById('maxPages');
            if (inputEl) {{
                maxPages = Math.max(1, Math.min(500, parseInt(inputEl.value) || 10));
                inputEl.value = maxPages;
            }}
            var pagesEl = document.getElementById('pagesValue');
            var cmdEl = document.getElementById('rescanCommand');
            if (pagesEl) pagesEl.textContent = maxPages;
            if (cmdEl) cmdEl.textContent = 'python checker.py ' + BASE_URL + ' --max-pages ' + maxPages + ' --format html';
        }}
        
        function copyCommand() {{
            var cmdEl = document.getElementById('rescanCommand');
            if (cmdEl && navigator.clipboard) {{
                navigator.clipboard.writeText(cmdEl.textContent).then(function() {{ alert('Kommando kopiert!'); }});
            }}
        }}
        
        document.addEventListener('click', function(e) {{
            if (e.target && e.target.id === 'rescanModal') closeRescanModal();
        }});
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') closeRescanModal();
        }});
        
        document.addEventListener('DOMContentLoaded', function() {{
            applyFilters();
        }});
    </script>
</head>
<body>
    <div class="header">
        <h1>WCAG 2.1 Tilgjengelighetsrapport</h1>
        <p>Basert på testregler fra Tilsynet for universell utforming av IKT</p>
        <p><strong>Nettsted:</strong> {result.base_url}</p>
        <p><strong>Dato:</strong> {result.timestamp}</p>
    </div>
    
    {self._generate_statement_section_html(result)}
    
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
        <div class="stat pages-control" onclick="showRescanModal()" title="Klikk for ny skanning">
            <div class="stat-value">
                <span id="pagesValue">{summary['pages_checked']}</span>
                <div class="pages-adjust">
                    <button onclick="event.stopPropagation(); adjustPages(5)" title="+5">▲</button>
                    <button onclick="event.stopPropagation(); adjustPages(-5)" title="-5">▼</button>
                </div>
            </div>
            <div class="stat-label">Sider testet</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="visibleTotal">{summary['issues']}</div>
            <div class="stat-label">Synlige avvik</div>
        </div>
        <div class="stat critical filterable active" data-severity="critical" onclick="toggleFilter('critical')">
            <div class="stat-value">{summary['critical']}</div>
            <div class="stat-label">Kritiske</div>
        </div>
        <div class="stat serious filterable active" data-severity="serious" onclick="toggleFilter('serious')">
            <div class="stat-value">{summary['serious']}</div>
            <div class="stat-label">Alvorlige</div>
        </div>
        <div class="stat moderate filterable active" data-severity="moderate" onclick="toggleFilter('moderate')">
            <div class="stat-value">{summary['moderate']}</div>
            <div class="stat-label">Moderate</div>
        </div>
        <div class="stat minor filterable active" data-severity="minor" onclick="toggleFilter('minor')">
            <div class="stat-value">{summary['minor']}</div>
            <div class="stat-label">Mindre</div>
        </div>
        <div class="stat passed">
            <div class="stat-value">{summary['passed']}</div>
            <div class="stat-label">Bestått</div>
        </div>
        <div class="stat rescan-btn" onclick="showRescanModal()">
            <div class="stat-value">🔄</div>
            <div class="stat-label">Skann på nytt</div>
        </div>
    </div>
    
    <div class="filter-status">
        <div class="filter-status-text">
            Viser <strong id="visibleCount">{summary['issues']}</strong> av {summary['issues']} avvik
        </div>
        <div class="filter-actions">
            <button class="filter-action-btn" onclick="selectAll()">✓ Alle på</button>
            <button class="filter-action-btn" onclick="selectNone()">✗ Alle av</button>
            <button class="filter-action-btn" onclick="expandAll()">📂 Utvid</button>
            <button class="filter-action-btn" onclick="collapseAll()">📁 Lukk</button>
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
                        # Add data-severity attribute for filtering
                        html += f"""
            <div class="issue {issue.impact}" data-severity="{issue.impact}">
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
        
        # Add modal and footer
        html += f"""
    <div class="footer">
        <p>Testreglene er basert på <a href="https://www.uutilsynet.no/regelverk/oversikt-over-testregler-nettsteder/709" target="_blank">UU-tilsynets offisielle testregler</a></p>
    </div>

    <div class="modal-overlay" id="rescanModal">
        <div class="modal">
            <h3>🔄 Start ny skanning</h3>
            <div class="modal-url">{result.base_url}</div>
            <div class="modal-pages">
                <label>Antall sider:</label>
                <input type="number" id="maxPages" value="{summary['pages_checked']}" min="1" max="500" onchange="updateCommand()">
                <span class="modal-pages-hint">1-500</span>
            </div>
            <p style="font-size:13px;color:#666;margin:0 0 8px">Kopier kommandoen:</p>
            <div class="modal-command" id="rescanCommand">python checker.py {result.base_url} --max-pages {summary['pages_checked']} --format html</div>
            <div class="modal-actions">
                <button class="modal-btn secondary" onclick="closeRescanModal()">Lukk</button>
                <button class="modal-btn primary" onclick="copyCommand()">📋 Kopier</button>
            </div>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def _generate_statement_section_html(self, result: SiteResult) -> str:
        """Generate accessibility statement section HTML."""
        if not result.accessibility_statement:
            return ""
        
        stmt = result.accessibility_statement
        html = """
    <div class="statement-section">
        <h2>📋 Tilgjengelighetserklæring Status</h2>
        <div class="statement-status">
"""
        if stmt.has_statement_page:
            html += '            <div class="statement-item success">✅ <strong>Tilgjengelighetserklæring funnet</strong></div>\n'
            if stmt.statement_page_url:
                html += f'            <div class="statement-item">🔗 <a href="{stmt.statement_page_url}" class="statement-link" target="_blank">Gå til erklæring</a></div>\n'
            if stmt.uustatus_url:
                html += '            <div class="statement-item success">✅ <strong>Registrert på uustatus.no</strong></div>\n'
                html += f'            <div class="statement-item">🔗 <a href="{stmt.uustatus_url}" class="statement-link" target="_blank">Se på uustatus.no</a></div>\n'
            if stmt.is_current:
                date_str = f" ({stmt.last_updated[:10]})" if stmt.last_updated else ""
                html += f'            <div class="statement-item success">✅ <strong>Oppdatert{date_str}</strong></div>\n'
            elif stmt.last_updated:
                html += f'            <div class="statement-item warning">⚠️ Kan være utdatert (sist oppdatert: {stmt.last_updated[:10]})</div>\n'
            if stmt.compliance_status:
                status_class = "success" if "full" in stmt.compliance_status.lower() else "warning"
                html += f'            <div class="statement-item {status_class}">📊 {stmt.compliance_status}</div>\n'
        else:
            html += '            <div class="statement-item error">❌ <strong>Ingen tilgjengelighetserklæring funnet</strong></div>\n'
        
        html += """        </div>
"""
        if stmt.organization_name:
            html += f"""        <div class="statement-details">
            <p><strong>Organisasjon:</strong> {stmt.organization_name}</p>
        </div>
"""
        html += """    </div>
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
        print("  --article-patterns  Comma-separated patterns that identify article pages")
        print("")
        print("Example:")
        print("  python checker.py https://example.com --max-pages 100 --format html")
        print("  python checker.py https://example.com --exclude '/old/,/archive/'")
        sys.exit(1)
    
    url = sys.argv[1]
    max_pages = 10
    output_format = "html"
    exclude_patterns = []
    dedupe_articles = True
    article_patterns = None
    
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
        elif args[i] == "--article-patterns" and i + 1 < len(args):
            article_patterns = [p.strip() for p in args[i + 1].split(',')]
            i += 2
        else:
            i += 1
    
    checker = WCAGChecker(
        exclude_patterns=exclude_patterns,
        dedupe_articles=dedupe_articles,
        article_patterns=article_patterns
    )
    
    print(f"Starting WCAG check for: {url}")
    print(f"Max pages: {max_pages}")
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
    ext = {"json": "json", "html": "html", "markdown": "md"}[output_format]
    filename = f"wcag_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\nReport saved to: {filename}")


if __name__ == "__main__":
    main()
