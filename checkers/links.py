"""
WCAG 2.4.4 Link Purpose Checker
Checks that links have descriptive text.
"""

from bs4 import BeautifulSoup
import re

RULE_INFO = {
    "2.4.4a": {
        "criterion": "2.4.4",
        "criterion_name": "Formål med lenke (i kontekst)",
        "criterion_name_en": "Link Purpose (In Context)",
        "level": "A",
    }
}

# Generic link texts that are not descriptive
GENERIC_LINK_TEXTS = [
    'les mer', 'read more', 'klikk her', 'click here', 'her', 'here',
    'mer', 'more', 'lenke', 'link', 'gå', 'go', 'trykk her', 'press here',
    'les', 'read', 'se mer', 'see more', 'åpne', 'open', 'vis', 'show',
]


def check_links(soup, url, **kwargs):
    """
    Check links for descriptive text and proper purpose.
    
    Returns tuple of (issues, passed, warnings).
    """
    issues = []
    passed = []
    warnings = []
    
    rule = RULE_INFO["2.4.4a"]
    
    # Find all links
    links = soup.find_all('a', href=True)
    
    generic_links = []
    empty_links = []
    good_links = 0
    
    for link in links:
        href = link.get('href', '')
        
        # Skip anchor links
        if href.startswith('#') and len(href) <= 1:
            continue
        
        # Get link text
        link_text = link.get_text(strip=True).lower()
        aria_label = link.get('aria-label', '').strip()
        title = link.get('title', '').strip()
        
        # Check for image-only links
        img = link.find('img')
        if img and not link_text:
            img_alt = img.get('alt', '').strip()
            if img_alt:
                link_text = img_alt.lower()
        
        # Effective link text
        effective_text = aria_label or link_text or title
        
        if not effective_text:
            empty_links.append(link)
        elif effective_text.lower() in GENERIC_LINK_TEXTS:
            generic_links.append((link, effective_text))
        else:
            good_links += 1
    
    # Report empty links
    for link in empty_links[:5]:
        href = link.get('href', '')[:100]
        element_str = str(link)[:200]
        issues.append({
            "rule_id": "2.4.4a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "critical",
            "element": element_str,
            "selector": _get_selector(link),
            "issue": f"Lenke uten tekst: {href}",
            "fix": "Legg til beskrivende lenketekst eller aria-label"
        })
    
    # Report generic links
    for link, text in generic_links[:5]:
        element_str = str(link)[:200]
        issues.append({
            "rule_id": "2.4.4a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "moderate",
            "element": element_str,
            "selector": _get_selector(link),
            "issue": f"Generisk lenketekst: '{text}'",
            "fix": "Bruk beskrivende lenketekst som forklarer hvor lenken fører"
        })
    
    # Check for redundant links (same href, different elements)
    # This is a common issue in card layouts
    href_counts = {}
    for link in links:
        href = link.get('href', '')
        if href and not href.startswith('#'):
            href_counts[href] = href_counts.get(href, 0) + 1
    
    redundant_count = sum(1 for count in href_counts.values() if count > 2)
    if redundant_count > 5:
        warnings.append({
            "rule_id": "2.4.4a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "minor",
            "element": "Multiple links",
            "selector": "",
            "issue": f"Fant {redundant_count} URL-er med mer enn 2 lenker. Vurder å konsolidere.",
            "fix": "Unngå mange lenker til samme URL - kan forvirre skjermleserbrukere"
        })
    
    # Summary
    total_issues = len(empty_links) + len(generic_links)
    if total_issues == 0 and len(links) > 0:
        passed.append({
            "rule_id": "2.4.4a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "message": f"Alle {len(links)} lenker har beskrivende tekst"
        })
    
    if len(empty_links) > 5 or len(generic_links) > 5:
        warnings.append({
            "rule_id": "2.4.4a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "moderate",
            "element": "Multiple links",
            "selector": "",
            "issue": f"Fant {len(empty_links)} tomme og {len(generic_links)} generiske lenker (viser kun de første 5 av hver)",
            "fix": "Gjennomgå alle lenker og forbedre lenketekstene"
        })
    
    return issues, passed, warnings


def _get_selector(element):
    """Generate a CSS-like selector for an element."""
    parts = []
    for parent in element.parents:
        if parent.name is None:
            break
        if parent.name == '[document]':
            break
        parts.append(parent.name)
    parts.reverse()
    parts.append(element.name)
    
    if element.get('id'):
        parts[-1] += f"#{element['id']}"
    elif element.get('class'):
        classes = element['class']
        if isinstance(classes, str):
            classes = classes.split()
        parts[-1] += f".{'.'.join(classes[:2])}"
    
    return ' > '.join(parts[-4:])
