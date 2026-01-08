"""
WCAG 1.4.11 Non-text Contrast Checker
Checks contrast for UI components and graphical objects.

Requirements:
- UI components (buttons, inputs, etc.) need 3:1 contrast
- Graphical objects that convey information need 3:1 contrast
- Focus indicators need 3:1 contrast
"""

import re
from bs4 import BeautifulSoup

# UU Test Rule mapping
RULE_INFO = {
    "1.4.11a": {
        "criterion": "1.4.11",
        "criterion_name": "Kontrast for ikke-tekstlig innhold",
        "criterion_name_en": "Non-text Contrast",
        "level": "AA",
    },
    "1.4.11b": {
        "criterion": "1.4.11",
        "criterion_name": "Kontrast for ikke-tekstlig innhold",
        "criterion_name_en": "Non-text Contrast",
        "level": "AA",
    },
}


def parse_color(color_str):
    """Parse CSS color string to RGB tuple."""
    if not color_str:
        return None
    
    color_str = color_str.strip().lower()
    
    # Named colors
    named_colors = {
        'white': (255, 255, 255),
        'black': (0, 0, 0),
        'red': (255, 0, 0),
        'green': (0, 128, 0),
        'blue': (0, 0, 255),
        'gray': (128, 128, 128),
        'grey': (128, 128, 128),
        'silver': (192, 192, 192),
        'transparent': None,
        'inherit': None,
        'none': None,
    }
    
    if color_str in named_colors:
        return named_colors[color_str]
    
    # Hex colors
    hex_match = re.match(r'^#([0-9a-f]{3}|[0-9a-f]{6})$', color_str)
    if hex_match:
        hex_val = hex_match.group(1)
        if len(hex_val) == 3:
            hex_val = ''.join([c*2 for c in hex_val])
        return tuple(int(hex_val[i:i+2], 16) for i in (0, 2, 4))
    
    # rgb() and rgba()
    rgb_match = re.match(r'^rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', color_str)
    if rgb_match:
        return tuple(int(rgb_match.group(i)) for i in (1, 2, 3))
    
    return None


def get_relative_luminance(rgb):
    """Calculate relative luminance per WCAG 2.1."""
    def channel_luminance(val):
        val = val / 255
        if val <= 0.03928:
            return val / 12.92
        return ((val + 0.055) / 1.055) ** 2.4
    
    r, g, b = rgb
    return 0.2126 * channel_luminance(r) + 0.7152 * channel_luminance(g) + 0.0722 * channel_luminance(b)


def get_contrast_ratio(color1, color2):
    """Calculate contrast ratio between two colors."""
    l1 = get_relative_luminance(color1)
    l2 = get_relative_luminance(color2)
    
    lighter = max(l1, l2)
    darker = min(l1, l2)
    
    return (lighter + 0.05) / (darker + 0.05)


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


def get_border_color(style):
    """Extract border color from style dict."""
    # Check specific border color
    for prop in ['border-color', 'border-top-color', 'border-bottom-color', 
                 'border-left-color', 'border-right-color']:
        if prop in style:
            color = parse_color(style[prop])
            if color:
                return color
    
    # Check border shorthand
    if 'border' in style:
        parts = style['border'].split()
        for part in parts:
            color = parse_color(part)
            if color:
                return color
    
    return None


def check_ui_component_contrast(element, soup, bg_color=(255, 255, 255)):
    """
    Check if a UI component has sufficient contrast.
    Returns (has_issue, issue_description).
    """
    style = parse_inline_style(element.get('style', ''))
    
    # Check border contrast for form elements
    if element.name in ('input', 'select', 'textarea'):
        border_color = get_border_color(style)
        
        if border_color:
            ratio = get_contrast_ratio(border_color, bg_color)
            if ratio < 3.0:
                return True, f"Kantlinjefarge har utilstrekkelig kontrast: {ratio:.2f}:1 (krav: 3:1)"
        
        # Check for very light borders (common issue)
        if not border_color:
            # Default browser borders are usually sufficient
            pass
    
    # Check button backgrounds
    if element.name == 'button' or element.get('role') == 'button':
        button_bg = style.get('background-color') or style.get('background', '')
        if button_bg:
            button_bg_color = parse_color(button_bg.split()[0] if button_bg else '')
            if button_bg_color:
                ratio = get_contrast_ratio(button_bg_color, bg_color)
                if ratio < 3.0:
                    return True, f"Knappebakgrunn har utilstrekkelig kontrast: {ratio:.2f}:1 (krav: 3:1)"
    
    return False, None


def check_focus_indicator(element, soup):
    """
    Check if element has visible focus indicator.
    This is a partial check - full verification requires interactive testing.
    """
    style = parse_inline_style(element.get('style', ''))
    
    # Check for outline:none or outline:0 (bad practice)
    outline = style.get('outline', '').lower()
    if 'none' in outline or outline == '0':
        return True, "Fokusindikator er fjernet (outline: none). Dette gjør det vanskelig å navigere med tastatur."
    
    return False, None


def check_non_text_contrast(soup, url, **kwargs):
    """
    Check non-text contrast for UI components and graphical objects.
    
    Returns tuple of (issues, passed, warnings).
    """
    issues = []
    passed = []
    warnings = []
    
    rule = RULE_INFO["1.4.11a"]
    
    # UI components to check
    ui_elements = []
    ui_elements.extend(soup.find_all('input'))
    ui_elements.extend(soup.find_all('select'))
    ui_elements.extend(soup.find_all('textarea'))
    ui_elements.extend(soup.find_all('button'))
    ui_elements.extend(soup.find_all(attrs={'role': 'button'}))
    ui_elements.extend(soup.find_all(attrs={'role': 'checkbox'}))
    ui_elements.extend(soup.find_all(attrs={'role': 'radio'}))
    
    checked_count = 0
    issue_count = 0
    focus_issues = []
    
    for element in ui_elements:
        # Skip hidden elements
        style = parse_inline_style(element.get('style', ''))
        if style.get('display') == 'none' or style.get('visibility') == 'hidden':
            continue
        
        # Skip hidden inputs
        if element.name == 'input' and element.get('type') == 'hidden':
            continue
        
        checked_count += 1
        
        # Check component contrast
        has_issue, issue_desc = check_ui_component_contrast(element, soup)
        if has_issue and issue_count < 5:
            issue_count += 1
            element_str = str(element)[:200]
            issues.append({
                "rule_id": "1.4.11a",
                "criterion_id": rule["criterion"],
                "criterion_name": rule["criterion_name"],
                "criterion_name_en": rule["criterion_name_en"],
                "level": rule["level"],
                "impact": "serious",
                "element": element_str,
                "selector": _get_selector(element),
                "issue": issue_desc,
                "fix": "Øk kontrasten til minst 3:1 mot bakgrunnen"
            })
        
        # Check focus indicator
        focus_issue, focus_desc = check_focus_indicator(element, soup)
        if focus_issue:
            focus_issues.append((element, focus_desc))
    
    # Report focus issues (separate from contrast)
    rule_b = RULE_INFO["1.4.11b"]
    for element, desc in focus_issues[:5]:
        element_str = str(element)[:200]
        issues.append({
            "rule_id": "1.4.11b",
            "criterion_id": rule_b["criterion"],
            "criterion_name": rule_b["criterion_name"],
            "criterion_name_en": rule_b["criterion_name_en"],
            "level": rule_b["level"],
            "impact": "serious",
            "element": element_str,
            "selector": _get_selector(element),
            "issue": desc,
            "fix": "Behold eller erstatt fokusindikator med synlig alternativ (f.eks. outline: 2px solid)"
        })
    
    if len(focus_issues) > 5:
        warnings.append({
            "rule_id": "1.4.11b",
            "criterion_id": rule_b["criterion"],
            "criterion_name": rule_b["criterion_name"],
            "criterion_name_en": rule_b["criterion_name_en"],
            "level": rule_b["level"],
            "impact": "moderate",
            "element": "Multiple elements",
            "selector": "",
            "issue": f"Fant {len(focus_issues)} elementer med fjernet fokusindikator (viser kun de første 5)",
            "fix": "Gjennomgå alle interaktive elementer og sørg for synlig fokusindikator"
        })
    
    # Add general warning about limitations
    if checked_count > 0:
        warnings.append({
            "rule_id": "1.4.11a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "minor",
            "element": "Page",
            "selector": "",
            "issue": f"Sjekket {checked_count} UI-komponenter. Denne testen er begrenset til inline-stiler. "
                     "Ikoner, grafikk og CSS-baserte stiler krever manuell kontroll.",
            "fix": "Bruk nettleserverktøy for fullstendig kontrastkontroll av UI-komponenter"
        })
    
    if checked_count > 0 and issue_count == 0 and len(focus_issues) == 0:
        passed.append({
            "rule_id": "1.4.11a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "message": f"Sjekket {checked_count} UI-komponenter - ingen åpenbare kontrastproblemer funnet"
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
