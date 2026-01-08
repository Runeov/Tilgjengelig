"""
WCAG 1.4.3 Contrast Checker
Checks text contrast ratios against backgrounds.

Requirements:
- Normal text: 4.5:1 minimum contrast ratio
- Large text (18pt/24px or 14pt/18.5px bold): 3:1 minimum
"""

import re
from bs4 import BeautifulSoup

# UU Test Rule mapping
RULE_INFO = {
    "1.4.3a": {
        "criterion": "1.4.3",
        "criterion_name": "Kontrast",
        "criterion_name_en": "Contrast (Minimum)",
        "level": "AA",
    }
}


def parse_color(color_str):
    """Parse CSS color string to RGB tuple."""
    if not color_str:
        return None
    
    color_str = color_str.strip().lower()
    
    # Named colors (common ones)
    named_colors = {
        'white': (255, 255, 255),
        'black': (0, 0, 0),
        'red': (255, 0, 0),
        'green': (0, 128, 0),
        'blue': (0, 0, 255),
        'yellow': (255, 255, 0),
        'gray': (128, 128, 128),
        'grey': (128, 128, 128),
        'silver': (192, 192, 192),
        'navy': (0, 0, 128),
        'orange': (255, 165, 0),
        'purple': (128, 0, 128),
        'transparent': None,
        'inherit': None,
        'initial': None,
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


def get_font_size_px(font_size_str):
    """Convert font-size to pixels (approximate)."""
    if not font_size_str:
        return 16  # Default
    
    font_size_str = font_size_str.strip().lower()
    
    # Pixel values
    px_match = re.match(r'^([\d.]+)\s*px', font_size_str)
    if px_match:
        return float(px_match.group(1))
    
    # Point values (1pt ≈ 1.333px)
    pt_match = re.match(r'^([\d.]+)\s*pt', font_size_str)
    if pt_match:
        return float(pt_match.group(1)) * 1.333
    
    # Em values (assume 16px base)
    em_match = re.match(r'^([\d.]+)\s*em', font_size_str)
    if em_match:
        return float(em_match.group(1)) * 16
    
    # Rem values
    rem_match = re.match(r'^([\d.]+)\s*rem', font_size_str)
    if rem_match:
        return float(rem_match.group(1)) * 16
    
    # Keyword sizes (approximate)
    keyword_sizes = {
        'xx-small': 9, 'x-small': 10, 'small': 13, 'medium': 16,
        'large': 18, 'x-large': 24, 'xx-large': 32
    }
    if font_size_str in keyword_sizes:
        return keyword_sizes[font_size_str]
    
    return 16


def is_large_text(font_size_px, is_bold=False):
    """Check if text qualifies as large text per WCAG."""
    # Large text: 18pt (24px) or 14pt (18.5px) bold
    if is_bold:
        return font_size_px >= 18.5
    return font_size_px >= 24


def get_element_colors(element, soup):
    """
    Try to determine foreground and background colors for an element.
    This is a simplified check - full accuracy requires browser rendering.
    """
    # Start with defaults (black on white)
    fg_color = (0, 0, 0)  # black
    bg_color = (255, 255, 255)  # white
    
    # Check inline styles
    style = parse_inline_style(element.get('style', ''))
    
    if 'color' in style:
        parsed = parse_color(style['color'])
        if parsed:
            fg_color = parsed
    
    if 'background-color' in style:
        parsed = parse_color(style['background-color'])
        if parsed:
            bg_color = parsed
    elif 'background' in style:
        # Try to extract color from background shorthand
        bg_val = style['background']
        for part in bg_val.split():
            parsed = parse_color(part)
            if parsed:
                bg_color = parsed
                break
    
    # Check parent elements for inherited colors
    for parent in element.parents:
        if parent.name is None:
            break
        parent_style = parse_inline_style(parent.get('style', ''))
        
        # Inherit color if not set
        if fg_color == (0, 0, 0) and 'color' in parent_style:
            parsed = parse_color(parent_style['color'])
            if parsed:
                fg_color = parsed
        
        # Background from parent (if our bg is still white/default)
        if bg_color == (255, 255, 255):
            if 'background-color' in parent_style:
                parsed = parse_color(parent_style['background-color'])
                if parsed:
                    bg_color = parsed
            elif 'background' in parent_style:
                for part in parent_style['background'].split():
                    parsed = parse_color(part)
                    if parsed:
                        bg_color = parsed
                        break
    
    return fg_color, bg_color


def check_contrast(soup, url, **kwargs):
    """
    Check color contrast for text elements.
    
    Returns tuple of (issues, passed, warnings).
    """
    issues = []
    passed = []
    warnings = []
    
    rule = RULE_INFO["1.4.3a"]
    
    # Elements to check for contrast
    text_elements = soup.find_all(['p', 'span', 'div', 'li', 'td', 'th', 'label', 
                                    'a', 'button', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    
    checked_count = 0
    issue_count = 0
    
    for element in text_elements:
        # Skip if no visible text
        text = element.get_text(strip=True)
        if not text or len(text) < 2:
            continue
        
        # Skip hidden elements
        style = parse_inline_style(element.get('style', ''))
        if style.get('display') == 'none' or style.get('visibility') == 'hidden':
            continue
        
        # Get colors
        fg_color, bg_color = get_element_colors(element, soup)
        
        # Calculate contrast ratio
        ratio = get_contrast_ratio(fg_color, bg_color)
        
        # Determine if large text
        font_size = get_font_size_px(style.get('font-size', ''))
        font_weight = style.get('font-weight', '')
        is_bold = font_weight in ('bold', '700', '800', '900') or element.name in ('h1', 'h2', 'h3', 'b', 'strong')
        large = is_large_text(font_size, is_bold)
        
        # Required ratio
        required_ratio = 3.0 if large else 4.5
        
        checked_count += 1
        
        if ratio < required_ratio:
            issue_count += 1
            
            # Only report first 10 issues per page to avoid spam
            if issue_count <= 10:
                element_str = str(element)[:200]
                issues.append({
                    "rule_id": "1.4.3a",
                    "criterion_id": rule["criterion"],
                    "criterion_name": rule["criterion_name"],
                    "criterion_name_en": rule["criterion_name_en"],
                    "level": rule["level"],
                    "impact": "serious",
                    "element": element_str,
                    "selector": _get_selector(element),
                    "issue": f"Utilstrekkelig kontrast: {ratio:.2f}:1 (krav: {required_ratio}:1). "
                             f"Forgrunns: rgb{fg_color}, Bakgrunn: rgb{bg_color}",
                    "fix": f"Øk kontrasten mellom tekst og bakgrunn til minst {required_ratio}:1"
                })
    
    # Add warning if we found issues
    if issue_count > 10:
        warnings.append({
            "rule_id": "1.4.3a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "moderate",
            "element": "Multiple elements",
            "selector": "",
            "issue": f"Fant {issue_count} elementer med utilstrekkelig kontrast (viser kun de første 10)",
            "fix": "Gjennomgå alle tekstelementer og sørg for tilstrekkelig kontrast"
        })
    
    if checked_count > 0 and issue_count == 0:
        passed.append({
            "rule_id": "1.4.3a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "message": f"Sjekket {checked_count} tekstelementer med tilstrekkelig kontrast"
        })
    
    # Add warning about limitations
    if checked_count > 0:
        warnings.append({
            "rule_id": "1.4.3a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "minor",
            "element": "Page",
            "selector": "",
            "issue": "Kontrastsjekk er basert på inline-stiler. Eksterne CSS-stiler ble ikke analysert. "
                     "Bruk nettleserverktøy for fullstendig kontrastkontroll.",
            "fix": "Kjør manuell kontrastsjekk med verktøy som WAVE, axe eller Chrome DevTools"
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
        parts[-1] += f".{'.'.join(element['class'][:2])}"
    
    return ' > '.join(parts[-4:])  # Last 4 levels
