"""
WCAG 1.4.1 Use of Color Checker
Ensures links are distinguishable by more than just color.

Requirements:
- Links in body text must have underline OR
- 3:1 contrast with surrounding text AND visual change on hover/focus
"""

import re
from bs4 import BeautifulSoup

# UU Test Rule mapping  
RULE_INFO = {
    "1.4.1a": {
        "criterion": "1.4.1",
        "criterion_name": "Bruk av farge",
        "criterion_name_en": "Use of Color",
        "level": "A",
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


def is_in_navigation(element):
    """Check if element is inside navigation context where links are obvious."""
    nav_containers = ['nav', 'header', 'footer', 'aside']
    nav_classes = ['nav', 'menu', 'navigation', 'navbar', 'header', 'footer', 
                   'sidebar', 'breadcrumb', 'pagination', 'tabs']
    nav_roles = ['navigation', 'menu', 'menubar', 'tablist']
    
    for parent in element.parents:
        if parent.name is None:
            break
        
        # Check tag name
        if parent.name in nav_containers:
            return True
        
        # Check class
        parent_classes = parent.get('class', [])
        if isinstance(parent_classes, str):
            parent_classes = parent_classes.split()
        for cls in parent_classes:
            if any(nav_word in cls.lower() for nav_word in nav_classes):
                return True
        
        # Check role
        if parent.get('role', '').lower() in nav_roles:
            return True
        
        # Check common navigation IDs
        parent_id = parent.get('id', '').lower()
        if any(nav_word in parent_id for nav_word in nav_classes):
            return True
    
    return False


def has_underline(element):
    """Check if link has underline decoration."""
    style = parse_inline_style(element.get('style', ''))
    
    # Check for explicit underline
    text_decoration = style.get('text-decoration', '').lower()
    if 'underline' in text_decoration:
        return True
    
    # Check for explicit removal of underline
    if 'none' in text_decoration:
        return False
    
    # Default browser behavior is to underline links
    # But many sites remove this in CSS, so we can't assume
    return None  # Unknown - depends on CSS


def has_non_color_indicator(element):
    """Check if link has visual indicator besides color."""
    style = parse_inline_style(element.get('style', ''))
    
    # Check for underline
    text_decoration = style.get('text-decoration', '').lower()
    if 'underline' in text_decoration:
        return True
    
    # Check for border (sometimes used as underline alternative)
    border_bottom = style.get('border-bottom', '')
    if border_bottom and border_bottom != 'none':
        return True
    
    # Check for font-weight (bold links)
    font_weight = style.get('font-weight', '').lower()
    if font_weight in ('bold', '700', '800', '900'):
        return True
    
    # Check for background
    background = style.get('background', '') or style.get('background-color', '')
    if background and background not in ('none', 'transparent', 'inherit'):
        return True
    
    return False


def is_in_body_text(element):
    """Check if link is within body text (paragraph, list, etc.)."""
    # Links in body text are the ones that need visual distinction
    body_text_parents = ['p', 'li', 'dd', 'td', 'th', 'article', 'section', 'main', 'div']
    
    for parent in element.parents:
        if parent.name is None:
            break
        if parent.name in body_text_parents:
            # Check if parent has substantial text
            parent_text = parent.get_text(strip=True)
            link_text = element.get_text(strip=True)
            # If link is not the only content, it's inline text
            if len(parent_text) > len(link_text) + 10:
                return True
    
    return False


def check_use_of_color(soup, url, **kwargs):
    """
    Check that links are distinguishable by more than just color.
    
    Returns tuple of (issues, passed, warnings).
    """
    issues = []
    passed = []
    warnings = []
    
    rule = RULE_INFO["1.4.1a"]
    
    # Find all links
    links = soup.find_all('a', href=True)
    
    problem_links = []
    checked_count = 0
    nav_link_count = 0
    
    for link in links:
        # Skip empty links
        link_text = link.get_text(strip=True)
        if not link_text:
            continue
        
        # Skip links that are clearly in navigation (exempt from this rule)
        if is_in_navigation(link):
            nav_link_count += 1
            continue
        
        # Only check links that are in body text context
        if not is_in_body_text(link):
            continue
        
        checked_count += 1
        
        # Check for visual indicators
        style = parse_inline_style(link.get('style', ''))
        
        # Check if underline is explicitly removed
        text_decoration = style.get('text-decoration', '').lower()
        underline_removed = 'none' in text_decoration
        
        # Check for other visual indicators
        has_other_indicator = has_non_color_indicator(link)
        
        # If underline is explicitly removed and no other indicator found
        if underline_removed and not has_other_indicator:
            problem_links.append(link)
    
    # Report issues (limit to 10)
    for link in problem_links[:10]:
        link_text = link.get_text(strip=True)[:50]
        element_str = str(link)[:200]
        
        issues.append({
            "rule_id": "1.4.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "serious",
            "element": element_str,
            "selector": _get_selector(link),
            "issue": f"Lenke '{link_text}' er ikke understreket og skiller seg kun ut med farge. "
                     "Dette gjør det vanskelig for fargeblinde å identifisere lenker.",
            "fix": "Legg til understreking (text-decoration: underline) eller annen visuell indikator som ikke er farge"
        })
    
    if len(problem_links) > 10:
        warnings.append({
            "rule_id": "1.4.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "moderate",
            "element": "Multiple links",
            "selector": "",
            "issue": f"Fant {len(problem_links)} lenker uten understreking (viser kun de første 10)",
            "fix": "Gjennomgå alle lenker og sørg for visuell distinksjon utover farge"
        })
    
    if checked_count > 0 and len(problem_links) == 0:
        passed.append({
            "rule_id": "1.4.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "message": f"Sjekket {checked_count} lenker i brødtekst - alle har visuell distinksjon"
        })
    
    # Add note about CSS-based underlines
    if checked_count > 0:
        warnings.append({
            "rule_id": "1.4.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "minor",
            "element": "Page",
            "selector": "",
            "issue": f"Sjekket {checked_count} lenker i brødtekst. {nav_link_count} navigasjonslenker ble hoppet over. "
                     "Denne testen sjekker kun inline-stiler. CSS-baserte stiler krever manuell sjekk.",
            "fix": "Verifiser manuelt at lenker er tydelig synlige i nettleseren"
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
