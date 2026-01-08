"""
WCAG Use of Color Accessibility Checker
Covers: 1.4.1 Use of Color
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


def check_use_of_color(soup, url, html=None):
    """Check for proper use of color (not as sole means of conveying info)."""
    issues = []
    passed = []
    warnings = []
    
    # Check links - should be distinguishable not just by color
    links = soup.find_all('a')
    for link in links:
        # Check if link has underline or other visual indicator
        style = link.get('style', '')
        classes = ' '.join(link.get('class', []))
        
        # Check for text-decoration: none (removes underline)
        if 'text-decoration' in style.lower() and 'none' in style.lower():
            if 'underline' not in style.lower():  # Not re-added
                warnings.append(f"1.4.1: Link may rely only on color - underline removed: {link.get_text()[:30]}")
    
    # Check for color-only indicators in text
    if html:
        color_only_patterns = [
            (r'(red|green|blue|yellow|orange)\s+(text|items?|fields?|required)', 
             "Text references color for identification"),
            (r'(highlighted|marked)\s+in\s+(red|green|blue|yellow)',
             "Content identified only by color highlighting"),
            (r'(errors?|required)\s+.{0,20}\s+(shown|displayed|marked)\s+in\s+(red|green)',
             "Errors or required fields may be indicated by color alone"),
        ]
        
        for pattern, description in color_only_patterns:
            if re.search(pattern, html, re.I):
                warnings.append(f"1.4.1: {description}")
    
    # Check form error indicators
    error_classes = ['error', 'invalid', 'danger', 'warning']
    for cls in error_classes:
        elements = soup.find_all(class_=re.compile(cls, re.I))
        for elem in elements:
            # Check if element has additional indicator (icon, text, border)
            has_icon = elem.find(['svg', 'i', 'span'], class_=re.compile(r'icon|fa-|material'))
            has_text = any(x in elem.get_text().lower() for x in ['error', 'feil', 'required', 'påkrevd'])
            
            if not has_icon and not has_text:
                warnings.append(f"1.4.1: Element with '{cls}' class may rely only on color")
    
    # Check for status indicators
    status_classes = ['success', 'error', 'warning', 'info', 'active', 'inactive']
    for cls in status_classes:
        elements = soup.find_all(class_=re.compile(f'^{cls}$|\\b{cls}\\b', re.I))
        if elements:
            warnings.append(f"1.4.1: Found {len(elements)} elements with '{cls}' status - ensure not color-only")
    
    # Check pie charts, graphs (canvas/svg)
    charts = soup.find_all(['canvas', 'svg'])
    for chart in charts:
        classes = ' '.join(chart.get('class', []))
        if any(x in classes.lower() for x in ['chart', 'graph', 'pie', 'bar']):
            issues.append(Issue(
                rule_id="1.4.1",
                criterion_id="1.4.1",
                criterion_name="Bruk av farge",
                criterion_name_en="Use of Color",
                level="A",
                impact="moderate",
                element=str(chart)[:200],
                selector=chart.name,
                issue="Chart/graph found - ensure data is not conveyed by color alone",
                fix="Add patterns, labels, or other visual indicators in addition to color"
            ))
    
    # Check for color-coded navigation
    navs = soup.find_all('nav')
    for nav in navs:
        active = nav.find_all(class_=re.compile(r'active|current|selected', re.I))
        for item in active:
            style = item.get('style', '')
            # Check if active state has more than color
            has_border = 'border' in style.lower()
            has_bg = 'background' in style.lower()
            has_underline = 'underline' in style.lower()
            has_icon = item.find(['svg', 'i'])
            
            if not (has_border or has_underline or has_icon):
                warnings.append("1.4.1: Navigation active state may rely only on color")
    
    # Check legend/key elements
    legends = soup.find_all(class_=re.compile(r'legend|key', re.I))
    if legends:
        warnings.append("1.4.1: Legend/key found - ensure it doesn't rely on color alone")
    
    # General pass if no specific issues found
    if not issues and not warnings:
        passed.append("1.4.1: No obvious color-only indicators found (manual review recommended)")
    
    return issues, passed, warnings
