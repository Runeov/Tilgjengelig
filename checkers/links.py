"""
WCAG Links Accessibility Checker
Covers: 2.4.4 Link Purpose (In Context)
"""

from dataclasses import dataclass
import re


@dataclass
class Issue:
    rule_id: str
    criterion_id: str
    criterion_name: str
    criterion_name_en: str
    level: str
    impact: str
    element: str
    selector: str
    issue: str
    fix: str
    context: str = ""


def check_links(soup, url, html=None):
    """Check links for accessibility issues."""
    issues = []
    passed = []
    warnings = []
    
    # Generic/unclear link texts
    GENERIC_TEXTS = {
        'click here', 'here', 'read more', 'les mer', 'more', 'mer',
        'link', 'lenke', 'learn more', 'lær mer', 'info', 'details',
        'this', 'denne', 'click', 'klikk', 'klikk her', 'last ned', 'download'
    }
    
    REDUNDANT_PHRASES = [
        'link to', 'lenke til', 'go to', 'gå til', 'click to',
        'click here to', 'klikk her for å'
    ]
    
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        element_str = str(a)[:200]
        
        # Get accessible name
        text = a.get_text(strip=True)
        aria_label = a.get('aria-label', '')
        title = a.get('title', '')
        
        # Check images inside link for alt text
        img = a.find('img')
        img_alt = img.get('alt', '') if img else ''
        
        accessible_name = aria_label or text or img_alt or title
        
        # Check for empty links
        if not accessible_name:
            issues.append(Issue(
                rule_id="2.4.4",
                criterion_id="2.4.4",
                criterion_name="Formål med lenke",
                criterion_name_en="Link Purpose (In Context)",
                level="A",
                impact="critical",
                element=element_str,
                selector=f'a[href="{href[:50]}"]',
                issue="Link has no accessible name (empty link)",
                fix="Add text content, aria-label, or image with alt text"
            ))
            continue
        
        # Check for generic link text
        if accessible_name.lower().strip() in GENERIC_TEXTS:
            issues.append(Issue(
                rule_id="2.4.4",
                criterion_id="2.4.4",
                criterion_name="Formål med lenke",
                criterion_name_en="Link Purpose (In Context)",
                level="A",
                impact="serious",
                element=element_str,
                selector=f'a[href="{href[:50]}"]',
                issue=f"Link text is not descriptive: '{accessible_name}'",
                fix="Use descriptive text that indicates where the link goes (e.g., 'Read more about products' instead of 'Read more')"
            ))
        # Check for redundant phrases
        elif any(phrase in accessible_name.lower() for phrase in REDUNDANT_PHRASES):
            issues.append(Issue(
                rule_id="2.4.4",
                criterion_id="2.4.4",
                criterion_name="Formål med lenke",
                criterion_name_en="Link Purpose (In Context)",
                level="A",
                impact="minor",
                element=element_str,
                selector=f'a[href="{href[:50]}"]',
                issue=f"Link text has redundant phrase: '{accessible_name}'",
                fix="Remove 'link to' or similar - screen readers already announce it as a link"
            ))
        # Check for URL as link text
        elif re.match(r'^https?://', accessible_name) or accessible_name.startswith('www.'):
            issues.append(Issue(
                rule_id="2.4.4",
                criterion_id="2.4.4",
                criterion_name="Formål med lenke",
                criterion_name_en="Link Purpose (In Context)",
                level="A",
                impact="moderate",
                element=element_str,
                selector=f'a[href="{href[:50]}"]',
                issue="Link text is a URL",
                fix="Replace URL with descriptive text that explains the link destination"
            ))
        # Check for very long link text
        elif len(accessible_name) > 100:
            issues.append(Issue(
                rule_id="2.4.4",
                criterion_id="2.4.4",
                criterion_name="Formål med lenke",
                criterion_name_en="Link Purpose (In Context)",
                level="A",
                impact="minor",
                element=element_str,
                selector=f'a[href="{href[:50]}"]',
                issue=f"Link text is very long ({len(accessible_name)} characters)",
                fix="Shorten link text to be concise while remaining descriptive"
            ))
        else:
            passed.append(f"2.4.4: Link has descriptive text: {accessible_name[:30]}")
        
        # Check for target="_blank" without indication
        if a.get('target') == '_blank':
            if 'new window' not in accessible_name.lower() and \
               'new tab' not in accessible_name.lower() and \
               'nytt vindu' not in accessible_name.lower() and \
               'ny fane' not in accessible_name.lower():
                # Check for visually hidden text or icon
                sr_text = a.find(class_=re.compile(r'sr-only|visually-hidden|screen-reader'))
                if not sr_text:
                    issues.append(Issue(
                        rule_id="2.4.4",
                        criterion_id="2.4.4",
                        criterion_name="Formål med lenke",
                        criterion_name_en="Link Purpose (In Context)",
                        level="A",
                        impact="moderate",
                        element=element_str,
                        selector=f'a[href="{href[:50]}"]',
                        issue="Link opens in new window without indication",
                        fix="Add text like '(opens in new tab)' or use visually-hidden text for screen readers"
                    ))
        
        # Check for javascript: links
        if href.startswith('javascript:'):
            issues.append(Issue(
                rule_id="2.4.4",
                criterion_id="2.4.4",
                criterion_name="Formål med lenke",
                criterion_name_en="Link Purpose (In Context)",
                level="A",
                impact="moderate",
                element=element_str,
                selector=f'a[href^="javascript:"]',
                issue="Link uses javascript: URL",
                fix="Use a button element for actions, or use href with progressive enhancement"
            ))
        
        # Check for # links with onclick (should be buttons)
        if href == '#' and a.get('onclick'):
            issues.append(Issue(
                rule_id="2.4.4",
                criterion_id="2.4.4",
                criterion_name="Formål med lenke",
                criterion_name_en="Link Purpose (In Context)",
                level="A",
                impact="moderate",
                element=element_str,
                selector='a[href="#"]',
                issue="Link with href='#' and onclick should be a button",
                fix="Use <button> element for interactive controls, or add role='button'"
            ))
    
    return issues, passed, warnings
