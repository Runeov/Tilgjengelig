"""
WCAG 1.3.1 Headings Checker
Checks heading structure and hierarchy.
"""

from bs4 import BeautifulSoup

RULE_INFO = {
    "1.3.1a": {
        "criterion": "1.3.1",
        "criterion_name": "Informasjon og relasjoner",
        "criterion_name_en": "Info and Relationships",
        "level": "A",
    }
}


def check_headings(soup, url, **kwargs):
    """
    Check heading structure for proper hierarchy.
    
    Returns tuple of (issues, passed, warnings).
    """
    issues = []
    passed = []
    warnings = []
    
    rule = RULE_INFO["1.3.1a"]
    
    # Find all headings
    headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    
    if not headings:
        warnings.append({
            "rule_id": "1.3.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "moderate",
            "element": "Page",
            "selector": "",
            "issue": "Siden har ingen overskrifter",
            "fix": "Legg til overskrifter (h1-h6) for å strukturere innholdet"
        })
        return issues, passed, warnings
    
    # Check for empty headings
    empty_headings = []
    for h in headings:
        text = h.get_text(strip=True)
        if not text:
            empty_headings.append(h)
    
    for h in empty_headings[:5]:
        element_str = str(h)[:200]
        issues.append({
            "rule_id": "1.3.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "serious",
            "element": element_str,
            "selector": _get_selector(h),
            "issue": f"Tom overskrift ({h.name})",
            "fix": "Legg til tekst i overskriften eller fjern den"
        })
    
    # Check for multiple h1
    h1_count = len(soup.find_all('h1'))
    if h1_count > 1:
        warnings.append({
            "rule_id": "1.3.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "moderate",
            "element": "Page",
            "selector": "",
            "issue": f"Siden har {h1_count} h1-overskrifter. Det anbefales kun én.",
            "fix": "Bruk kun én h1-overskrift per side"
        })
    elif h1_count == 0:
        issues.append({
            "rule_id": "1.3.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "serious",
            "element": "Page",
            "selector": "",
            "issue": "Siden mangler h1-overskrift",
            "fix": "Legg til en h1-overskrift som beskriver sidens hovedinnhold"
        })
    
    # Check heading hierarchy (skip levels)
    prev_level = 0
    skip_issues = []
    
    for h in headings:
        level = int(h.name[1])
        if prev_level > 0 and level > prev_level + 1:
            skip_issues.append((h, prev_level, level))
        prev_level = level
    
    for h, prev, curr in skip_issues[:3]:
        element_str = str(h)[:200]
        issues.append({
            "rule_id": "1.3.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "moderate",
            "element": element_str,
            "selector": _get_selector(h),
            "issue": f"Overskriftsnivå hoppes over: h{prev} til h{curr}",
            "fix": f"Bruk h{prev + 1} i stedet for h{curr} for å opprettholde riktig hierarki"
        })
    
    # Summary
    if len(empty_headings) == 0 and len(skip_issues) == 0 and h1_count == 1:
        passed.append({
            "rule_id": "1.3.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "message": f"Overskriftsstruktur OK: {len(headings)} overskrifter med riktig hierarki"
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
