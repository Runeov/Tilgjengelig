"""
WCAG 2.1.1 Keyboard Checker
Checks keyboard accessibility.
"""

from bs4 import BeautifulSoup
import re

RULE_INFO = {
    "2.1.1a": {
        "criterion": "2.1.1",
        "criterion_name": "Tastatur",
        "criterion_name_en": "Keyboard",
        "level": "A",
    },
    "2.4.7a": {
        "criterion": "2.4.7",
        "criterion_name": "Synlig fokus",
        "criterion_name_en": "Focus Visible",
        "level": "AA",
    }
}


def parse_inline_style(style_str):
    """Parse inline style attribute to dict."""
    if not style_str:
        return {}
    styles = {}
    for declaration in style_str.split(';'):
        if ':' in declaration:
            prop, val = declaration.split(':', 1)
            styles[prop.strip().lower()] = val.strip()
    return styles


def check_keyboard(soup, url, **kwargs):
    """
    Check keyboard accessibility issues.
    
    Returns tuple of (issues, passed, warnings).
    """
    issues = []
    passed = []
    warnings = []
    
    rule = RULE_INFO["2.1.1a"]
    
    # Check for tabindex > 0 (disrupts natural tab order)
    positive_tabindex = soup.find_all(attrs={'tabindex': re.compile(r'^[1-9]')})
    
    for element in positive_tabindex[:5]:
        tabindex = element.get('tabindex')
        element_str = str(element)[:200]
        issues.append({
            "rule_id": "2.1.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "serious",
            "element": element_str,
            "selector": _get_selector(element),
            "issue": f"Positiv tabindex ({tabindex}) forstyrrer naturlig tabuleringsrekkefølge",
            "fix": "Bruk tabindex='0' eller fjern tabindex helt. Ordne DOM-rekkefølgen i stedet."
        })
    
    # Check for elements with onclick but not keyboard accessible
    onclick_elements = soup.find_all(attrs={'onclick': True})
    
    non_focusable_with_click = []
    for element in onclick_elements:
        # Skip naturally focusable elements
        if element.name in ('a', 'button', 'input', 'select', 'textarea'):
            continue
        
        # Check if made focusable
        tabindex = element.get('tabindex')
        role = element.get('role', '')
        
        if tabindex is None and role not in ('button', 'link', 'checkbox', 'radio'):
            non_focusable_with_click.append(element)
    
    for element in non_focusable_with_click[:5]:
        element_str = str(element)[:200]
        issues.append({
            "rule_id": "2.1.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "critical",
            "element": element_str,
            "selector": _get_selector(element),
            "issue": f"Element ({element.name}) har onclick men er ikke tastaturtilgjengelig",
            "fix": "Legg til tabindex='0' og onkeypress/onkeydown handler, eller bruk <button>"
        })
    
    # Check for focus indicator removal
    focus_rule = RULE_INFO["2.4.7a"]
    elements_with_outline_none = []
    
    for element in soup.find_all(True):
        style = parse_inline_style(element.get('style', ''))
        outline = style.get('outline', '').lower()
        if 'none' in outline or outline == '0':
            elements_with_outline_none.append(element)
    
    for element in elements_with_outline_none[:5]:
        element_str = str(element)[:200]
        issues.append({
            "rule_id": "2.4.7a",
            "criterion_id": focus_rule["criterion"],
            "criterion_name": focus_rule["criterion_name"],
            "criterion_name_en": focus_rule["criterion_name_en"],
            "level": focus_rule["level"],
            "impact": "serious",
            "element": element_str,
            "selector": _get_selector(element),
            "issue": "Fokusindikator er fjernet (outline: none)",
            "fix": "Behold eller erstatt fokusindikator med synlig alternativ"
        })
    
    # Check for skip link
    first_link = soup.find('a', href=True)
    has_skip_link = False
    
    if first_link:
        href = first_link.get('href', '')
        text = first_link.get_text(strip=True).lower()
        if href.startswith('#') and ('hopp' in text or 'skip' in text or 'main' in text):
            has_skip_link = True
    
    if not has_skip_link:
        warnings.append({
            "rule_id": "2.4.1a",
            "criterion_id": "2.4.1",
            "criterion_name": "Hoppe over blokker",
            "criterion_name_en": "Bypass Blocks",
            "level": "A",
            "impact": "moderate",
            "element": "Page",
            "selector": "",
            "issue": "Ingen synlig 'hopp til hovedinnhold' lenke funnet",
            "fix": "Legg til en 'Hopp til hovedinnhold' lenke i starten av siden"
        })
    
    # Summary
    total_issues = len(positive_tabindex) + len(non_focusable_with_click) + len(elements_with_outline_none)
    if total_issues == 0:
        passed.append({
            "rule_id": "2.1.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "message": "Ingen åpenbare tastaturtilgjengelighetsproblemer funnet"
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
