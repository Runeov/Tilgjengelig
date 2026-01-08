"""
Accessibility Statement (Tilgjengelighetserklæring / Tilgjengelegheitserklæring) Checker

This module checks for the presence and validity of accessibility statements
as required by Norwegian law. It looks for:
1. The accessibility statement page on the site (typically /tilgjengelighet/ or /tilgjengelegheit/)
2. Links to uustatus.no declaration
3. When the declaration was last updated

Supports both Bokmal and Nynorsk variants:
- Bokmal: tilgjengelighet, tilgjengelighetserklæring
- Nynorsk: tilgjengelegheit, tilgjengelegheitserklæring

Requirements:
- All Norwegian public sector websites must have a published accessibility statement
- The statement must be linked from the uustatus.no portal
- The statement should be regularly updated (at least annually)
"""

import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests


@dataclass
class AccessibilityStatementResult:
    """Result of accessibility statement check."""
    has_statement_page: bool
    statement_page_url: Optional[str]
    has_uustatus_link: bool
    uustatus_url: Optional[str]
    uustatus_status: Optional[str]  # 'published', 'draft', 'expired', 'not_found'
    last_updated: Optional[str]
    days_since_update: Optional[int]
    is_current: bool  # True if updated within last 365 days
    organization_name: Optional[str]
    compliance_level: Optional[str]  # 'full', 'partial', 'not_compliant'
    errors: List[str]
    warnings: List[str]
    
    @property
    def summary(self) -> dict:
        """Return a summary of the check."""
        return {
            "has_statement": self.has_statement_page,
            "statement_url": self.statement_page_url,
            "has_uustatus": self.has_uustatus_link,
            "uustatus_url": self.uustatus_url,
            "status": self.uustatus_status,
            "last_updated": self.last_updated,
            "days_since_update": self.days_since_update,
            "is_current": self.is_current,
            "organization": self.organization_name,
            "compliance": self.compliance_level,
            "errors": self.errors,
            "warnings": self.warnings
        }


class AccessibilityStatementChecker:
    """Check for accessibility statement compliance."""
    
    # Common URL patterns for accessibility statement pages
    # Includes both Bokmal and Nynorsk variants
    STATEMENT_URL_PATTERNS = [
        # Bokmal variants
        '/tilgjengelighet',
        '/tilgjengelighet/',
        '/tilgjengelighetserklaring',
        '/tilgjengelighetserklæring',
        # Nynorsk variants
        '/tilgjengelegheit',
        '/tilgjengelegheit/',
        '/tilgjengelegheitserklaring',
        '/tilgjengelegheitserklæring',
        # Other common patterns
        '/universell-utforming',
        '/universell-utforming/',
        '/accessibility',
        '/accessibility/',
        '/uu-erklaering',
        '/personvern-og-tilgjengelighet',
        '/personvern-og-tilgjengelegheit',
    ]
    
    # Common link text patterns for accessibility statement
    # Includes both Bokmal and Nynorsk variants
    STATEMENT_LINK_TEXTS = [
        # Bokmal variants
        'tilgjengelighet',
        'tilgjengelighetserklæring',
        'tilgjengelighetserklaring',
        # Nynorsk variants
        'tilgjengelegheit',
        'tilgjengelegheitserklæring',
        'tilgjengelegheitserklaring',
        # Other common terms
        'universell utforming',
        'accessibility',
        'uu-erklæring',
        'uu-erklaring',
    ]
    
    def __init__(self, session: requests.Session = None, timeout: int = 30):
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "WCAGChecker/1.0 (Accessibility Statement Checker)"
        })
        self.timeout = timeout
    
    def check(self, base_url: str, html_content: str = None) -> AccessibilityStatementResult:
        """
        Check for accessibility statement on a website.
        
        Args:
            base_url: The base URL of the website to check
            html_content: Optional HTML content of the homepage (will be fetched if not provided)
        
        Returns:
            AccessibilityStatementResult with all findings
        """
        errors = []
        warnings = []
        
        # Normalize base URL
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url
        
        parsed = urlparse(base_url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"
        
        # Fetch homepage if not provided
        if html_content is None:
            try:
                response = self.session.get(base_url, timeout=self.timeout)
                response.raise_for_status()
                html_content = response.text
            except requests.RequestException as e:
                errors.append(f"Could not fetch homepage: {e}")
                return self._empty_result(errors, warnings)
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Step 1: Find the accessibility statement page
        statement_url = self._find_statement_page(soup, base_domain)
        
        if not statement_url:
            # Try common URL patterns directly
            statement_url = self._try_common_urls(base_domain)
        
        has_statement = statement_url is not None
        
        if not has_statement:
            errors.append("Ingen tilgjengelighetserklæring funnet på nettstedet")
        
        # Step 2: Fetch the statement page and look for uustatus.no link
        uustatus_url = None
        statement_page_content = None
        
        if statement_url:
            try:
                response = self.session.get(statement_url, timeout=self.timeout)
                response.raise_for_status()
                statement_page_content = response.text
                
                # Look for uustatus.no link
                uustatus_url = self._find_uustatus_link(statement_page_content)
                
            except requests.RequestException as e:
                warnings.append(f"Could not fetch statement page: {e}")
        
        has_uustatus = uustatus_url is not None
        
        if has_statement and not has_uustatus:
            warnings.append("Tilgjengelighetserklæringen har ikke lenke til uustatus.no")
        
        # Step 3: Fetch and parse uustatus.no declaration
        uustatus_status = None
        last_updated = None
        days_since_update = None
        is_current = False
        organization_name = None
        compliance_level = None
        
        if uustatus_url:
            uustatus_data = self._fetch_uustatus_declaration(uustatus_url)
            
            if uustatus_data:
                uustatus_status = uustatus_data.get('status')
                last_updated = uustatus_data.get('last_updated')
                days_since_update = uustatus_data.get('days_since_update')
                is_current = uustatus_data.get('is_current', False)
                organization_name = uustatus_data.get('organization')
                compliance_level = uustatus_data.get('compliance_level')
                
                if uustatus_data.get('errors'):
                    errors.extend(uustatus_data['errors'])
                if uustatus_data.get('warnings'):
                    warnings.extend(uustatus_data['warnings'])
            else:
                errors.append("Kunne ikke hente data fra uustatus.no")
        
        return AccessibilityStatementResult(
            has_statement_page=has_statement,
            statement_page_url=statement_url,
            has_uustatus_link=has_uustatus,
            uustatus_url=uustatus_url,
            uustatus_status=uustatus_status,
            last_updated=last_updated,
            days_since_update=days_since_update,
            is_current=is_current,
            organization_name=organization_name,
            compliance_level=compliance_level,
            errors=errors,
            warnings=warnings
        )
    
    def _empty_result(self, errors: List[str], warnings: List[str]) -> AccessibilityStatementResult:
        """Return an empty result with errors."""
        return AccessibilityStatementResult(
            has_statement_page=False,
            statement_page_url=None,
            has_uustatus_link=False,
            uustatus_url=None,
            uustatus_status=None,
            last_updated=None,
            days_since_update=None,
            is_current=False,
            organization_name=None,
            compliance_level=None,
            errors=errors,
            warnings=warnings
        )
    
    def _find_statement_page(self, soup: BeautifulSoup, base_domain: str) -> Optional[str]:
        """Find the accessibility statement page link in the HTML."""
        # Look for links in footer first (most common location)
        footers = soup.find_all(['footer', 'div'], class_=re.compile(r'footer|bunntekst', re.I))
        search_areas = footers + [soup]  # Search footers first, then whole page
        
        for area in search_areas:
            for a in area.find_all('a', href=True):
                href = a['href'].lower()
                link_text = a.get_text(strip=True).lower()
                
                # Check URL patterns
                for pattern in self.STATEMENT_URL_PATTERNS:
                    if pattern in href:
                        return urljoin(base_domain, a['href'])
                
                # Check link text
                for text_pattern in self.STATEMENT_LINK_TEXTS:
                    if text_pattern in link_text:
                        return urljoin(base_domain, a['href'])
        
        return None
    
    def _try_common_urls(self, base_domain: str) -> Optional[str]:
        """Try common accessibility statement URLs directly."""
        for pattern in self.STATEMENT_URL_PATTERNS[:5]:  # Try first 5 most common
            url = urljoin(base_domain, pattern)
            try:
                response = self.session.head(url, timeout=10, allow_redirects=True)
                if response.status_code == 200:
                    return response.url  # Return final URL after redirects
            except requests.RequestException:
                continue
        return None
    
    def _find_uustatus_link(self, html_content: str) -> Optional[str]:
        """Find uustatus.no link in the statement page."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look for uustatus.no links
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'uustatus.no' in href:
                return href
        
        # Also check for iframe embeds
        for iframe in soup.find_all('iframe', src=True):
            src = iframe['src']
            if 'uustatus.no' in src:
                return src
        
        return None
    
    def _fetch_uustatus_declaration(self, url: str) -> Optional[dict]:
        """Fetch and parse the uustatus.no declaration page."""
        result = {
            'status': None,
            'last_updated': None,
            'days_since_update': None,
            'is_current': False,
            'organization': None,
            'compliance_level': None,
            'errors': [],
            'warnings': []
        }
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            
            # Check if it's a published declaration
            if '/publisert/' in url:
                result['status'] = 'published'
            elif '/utkast/' in url or '/draft/' in url:
                result['status'] = 'draft'
                result['warnings'].append("Tilgjengelighetserklæringen er kun et utkast, ikke publisert")
            
            # Try to find the last updated date
            # uustatus.no typically shows this in various formats
            date_patterns = [
                r'Sist oppdatert[:\s]*(\d{1,2})[.\s](\d{1,2}|\w+)[.\s](\d{4})',
                r'Oppdatert[:\s]*(\d{1,2})[.\s](\d{1,2}|\w+)[.\s](\d{4})',
                r'(\d{1,2})[.\s](januar|februar|mars|april|mai|juni|juli|august|september|oktober|november|desember)[.\s](\d{4})',
                r'(\d{4})-(\d{2})-(\d{2})',
            ]
            
            page_text = soup.get_text()
            
            for pattern in date_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    try:
                        date_str = match.group(0)
                        parsed_date = self._parse_norwegian_date(date_str)
                        if parsed_date:
                            result['last_updated'] = parsed_date.strftime('%Y-%m-%d')
                            result['days_since_update'] = (datetime.now() - parsed_date).days
                            result['is_current'] = result['days_since_update'] <= 365
                            
                            if not result['is_current']:
                                result['warnings'].append(
                                    f"Tilgjengelighetserklæringen er utdatert ({result['days_since_update']} dager siden sist oppdatert)"
                                )
                            break
                    except Exception:
                        continue
            
            # Try to find organization name
            title = soup.find('title')
            if title:
                title_text = title.get_text()
                # Try to extract org name from title
                if '-' in title_text:
                    result['organization'] = title_text.split('-')[0].strip()
            
            # Look for h1 with organization name
            h1 = soup.find('h1')
            if h1:
                h1_text = h1.get_text(strip=True)
                if h1_text and len(h1_text) < 100:
                    result['organization'] = h1_text
            
            # Try to find compliance level
            compliance_keywords = {
                'full': ['fullt ut samsvar', 'oppfyller alle krav', 'full compliance'],
                'partial': ['delvis samsvar', 'delvis', 'partial compliance', 'noen avvik'],
                'not_compliant': ['ikke i samsvar', 'oppfyller ikke', 'ikke samsvar', 'not compliant']
            }
            
            page_text_lower = page_text.lower()
            for level, keywords in compliance_keywords.items():
                for keyword in keywords:
                    if keyword in page_text_lower:
                        result['compliance_level'] = level
                        break
                if result['compliance_level']:
                    break
            
            return result
            
        except requests.RequestException as e:
            result['errors'].append(f"Kunne ikke hente uustatus.no: {e}")
            result['status'] = 'not_found'
            return result
    
    def _parse_norwegian_date(self, date_str: str) -> Optional[datetime]:
        """Parse Norwegian date formats."""
        norwegian_months = {
            'januar': 1, 'februar': 2, 'mars': 3, 'april': 4,
            'mai': 5, 'juni': 6, 'juli': 7, 'august': 8,
            'september': 9, 'oktober': 10, 'november': 11, 'desember': 12
        }
        
        date_str = date_str.lower().strip()
        
        # Try ISO format first: 2024-01-15
        iso_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
        if iso_match:
            return datetime(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        
        # Try Norwegian format: 15. januar 2024
        nor_match = re.search(r'(\d{1,2})[.\s]*(januar|februar|mars|april|mai|juni|juli|august|september|oktober|november|desember)[.\s]*(\d{4})', date_str)
        if nor_match:
            day = int(nor_match.group(1))
            month = norwegian_months.get(nor_match.group(2))
            year = int(nor_match.group(3))
            if month:
                return datetime(year, month, day)
        
        # Try numeric format: 15.01.2024
        num_match = re.match(r'(\d{1,2})[.\s](\d{1,2})[.\s](\d{4})', date_str)
        if num_match:
            return datetime(int(num_match.group(3)), int(num_match.group(2)), int(num_match.group(1)))
        
        return None


def check_accessibility_statement(url: str, session: requests.Session = None) -> AccessibilityStatementResult:
    """
    Convenience function to check accessibility statement.
    
    Args:
        url: Website URL to check
        session: Optional requests session to use
    
    Returns:
        AccessibilityStatementResult
    """
    checker = AccessibilityStatementChecker(session=session)
    return checker.check(url)


def format_statement_report(result: AccessibilityStatementResult) -> str:
    """Format the accessibility statement check as a readable report."""
    lines = []
    lines.append("=" * 60)
    lines.append("TILGJENGELIGHETSERKLARING STATUS")
    lines.append("=" * 60)
    lines.append("")
    
    # Statement page
    if result.has_statement_page:
        lines.append(f"[OK] Tilgjengelighetserklaring funnet: {result.statement_page_url}")
    else:
        lines.append("[X] Ingen tilgjengelighetserklaring funnet pa nettstedet")
    
    lines.append("")
    
    # uustatus.no
    if result.has_uustatus_link:
        lines.append(f"[OK] Lenke til uustatus.no: {result.uustatus_url}")
        
        if result.uustatus_status:
            status_emoji = "[OK]" if result.uustatus_status == 'published' else "[!]"
            lines.append(f"   {status_emoji} Status: {result.uustatus_status}")
        
        if result.organization_name:
            lines.append(f"   [i] Organisasjon: {result.organization_name}")
        
        if result.last_updated:
            current_emoji = "[OK]" if result.is_current else "[!]"
            lines.append(f"   {current_emoji} Sist oppdatert: {result.last_updated}")
            if result.days_since_update is not None:
                lines.append(f"   [i] Dager siden oppdatering: {result.days_since_update}")
        
        if result.compliance_level:
            compliance_labels = {
                'full': '[OK] Fullt ut samsvar',
                'partial': '[!] Delvis samsvar',
                'not_compliant': '[X] Ikke i samsvar'
            }
            lines.append(f"   {compliance_labels.get(result.compliance_level, result.compliance_level)}")
    else:
        if result.has_statement_page:
            lines.append("[!] Tilgjengelighetserklaringen mangler lenke til uustatus.no")
        else:
            lines.append("[X] Ingen lenke til uustatus.no funnet")
    
    lines.append("")
    
    # Errors and warnings
    if result.errors:
        lines.append("[X] FEIL:")
        for error in result.errors:
            lines.append(f"   - {error}")
        lines.append("")
    
    if result.warnings:
        lines.append("[!] ADVARSLER:")
        for warning in result.warnings:
            lines.append(f"   - {warning}")
        lines.append("")
    
    lines.append("=" * 60)
    
    return "\n".join(lines)


# Main entry point for testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python accessibility_statement.py <url>")
        print("Example: python accessibility_statement.py https://www.oslo.kommune.no")
        sys.exit(1)
    
    url = sys.argv[1]
    print(f"Checking accessibility statement for: {url}")
    print()
    
    result = check_accessibility_statement(url)
    print(format_statement_report(result))
