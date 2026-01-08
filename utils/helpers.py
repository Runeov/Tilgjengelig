"""
Utility functions for WCAG checking.
Includes color contrast calculations, CSS parsing, etc.
"""

import re
from typing import Tuple, Optional


# Standard web colors
WEB_COLORS = {
    'aliceblue': (240, 248, 255), 'antiquewhite': (250, 235, 215), 'aqua': (0, 255, 255),
    'aquamarine': (127, 255, 212), 'azure': (240, 255, 255), 'beige': (245, 245, 220),
    'bisque': (255, 228, 196), 'black': (0, 0, 0), 'blanchedalmond': (255, 235, 205),
    'blue': (0, 0, 255), 'blueviolet': (138, 43, 226), 'brown': (165, 42, 42),
    'burlywood': (222, 184, 135), 'cadetblue': (95, 158, 160), 'chartreuse': (127, 255, 0),
    'chocolate': (210, 105, 30), 'coral': (255, 127, 80), 'cornflowerblue': (100, 149, 237),
    'cornsilk': (255, 248, 220), 'crimson': (220, 20, 60), 'cyan': (0, 255, 255),
    'darkblue': (0, 0, 139), 'darkcyan': (0, 139, 139), 'darkgoldenrod': (184, 134, 11),
    'darkgray': (169, 169, 169), 'darkgreen': (0, 100, 0), 'darkgrey': (169, 169, 169),
    'darkkhaki': (189, 183, 107), 'darkmagenta': (139, 0, 139), 'darkolivegreen': (85, 107, 47),
    'darkorange': (255, 140, 0), 'darkorchid': (153, 50, 204), 'darkred': (139, 0, 0),
    'darksalmon': (233, 150, 122), 'darkseagreen': (143, 188, 143), 'darkslateblue': (72, 61, 139),
    'darkslategray': (47, 79, 79), 'darkslategrey': (47, 79, 79), 'darkturquoise': (0, 206, 209),
    'darkviolet': (148, 0, 211), 'deeppink': (255, 20, 147), 'deepskyblue': (0, 191, 255),
    'dimgray': (105, 105, 105), 'dimgrey': (105, 105, 105), 'dodgerblue': (30, 144, 255),
    'firebrick': (178, 34, 34), 'floralwhite': (255, 250, 240), 'forestgreen': (34, 139, 34),
    'fuchsia': (255, 0, 255), 'gainsboro': (220, 220, 220), 'ghostwhite': (248, 248, 255),
    'gold': (255, 215, 0), 'goldenrod': (218, 165, 32), 'gray': (128, 128, 128),
    'green': (0, 128, 0), 'greenyellow': (173, 255, 47), 'grey': (128, 128, 128),
    'honeydew': (240, 255, 240), 'hotpink': (255, 105, 180), 'indianred': (205, 92, 92),
    'indigo': (75, 0, 130), 'ivory': (255, 255, 240), 'khaki': (240, 230, 140),
    'lavender': (230, 230, 250), 'lavenderblush': (255, 240, 245), 'lawngreen': (124, 252, 0),
    'lemonchiffon': (255, 250, 205), 'lightblue': (173, 216, 230), 'lightcoral': (240, 128, 128),
    'lightcyan': (224, 255, 255), 'lightgoldenrodyellow': (250, 250, 210), 'lightgray': (211, 211, 211),
    'lightgreen': (144, 238, 144), 'lightgrey': (211, 211, 211), 'lightpink': (255, 182, 193),
    'lightsalmon': (255, 160, 122), 'lightseagreen': (32, 178, 170), 'lightskyblue': (135, 206, 250),
    'lightslategray': (119, 136, 153), 'lightslategrey': (119, 136, 153), 'lightsteelblue': (176, 196, 222),
    'lightyellow': (255, 255, 224), 'lime': (0, 255, 0), 'limegreen': (50, 205, 50),
    'linen': (250, 240, 230), 'magenta': (255, 0, 255), 'maroon': (128, 0, 0),
    'mediumaquamarine': (102, 205, 170), 'mediumblue': (0, 0, 205), 'mediumorchid': (186, 85, 211),
    'mediumpurple': (147, 112, 219), 'mediumseagreen': (60, 179, 113), 'mediumslateblue': (123, 104, 238),
    'mediumspringgreen': (0, 250, 154), 'mediumturquoise': (72, 209, 204), 'mediumvioletred': (199, 21, 133),
    'midnightblue': (25, 25, 112), 'mintcream': (245, 255, 250), 'mistyrose': (255, 228, 225),
    'moccasin': (255, 228, 181), 'navajowhite': (255, 222, 173), 'navy': (0, 0, 128),
    'oldlace': (253, 245, 230), 'olive': (128, 128, 0), 'olivedrab': (107, 142, 35),
    'orange': (255, 165, 0), 'orangered': (255, 69, 0), 'orchid': (218, 112, 214),
    'palegoldenrod': (238, 232, 170), 'palegreen': (152, 251, 152), 'paleturquoise': (175, 238, 238),
    'palevioletred': (219, 112, 147), 'papayawhip': (255, 239, 213), 'peachpuff': (255, 218, 185),
    'peru': (205, 133, 63), 'pink': (255, 192, 203), 'plum': (221, 160, 221),
    'powderblue': (176, 224, 230), 'purple': (128, 0, 128), 'rebeccapurple': (102, 51, 153),
    'red': (255, 0, 0), 'rosybrown': (188, 143, 143), 'royalblue': (65, 105, 225),
    'saddlebrown': (139, 69, 19), 'salmon': (250, 128, 114), 'sandybrown': (244, 164, 96),
    'seagreen': (46, 139, 87), 'seashell': (255, 245, 238), 'sienna': (160, 82, 45),
    'silver': (192, 192, 192), 'skyblue': (135, 206, 235), 'slateblue': (106, 90, 205),
    'slategray': (112, 128, 144), 'slategrey': (112, 128, 144), 'snow': (255, 250, 250),
    'springgreen': (0, 255, 127), 'steelblue': (70, 130, 180), 'tan': (210, 180, 140),
    'teal': (0, 128, 128), 'thistle': (216, 191, 216), 'tomato': (255, 99, 71),
    'turquoise': (64, 224, 208), 'violet': (238, 130, 238), 'wheat': (245, 222, 179),
    'white': (255, 255, 255), 'whitesmoke': (245, 245, 245), 'yellow': (255, 255, 0),
    'yellowgreen': (154, 205, 50)
}


def parse_color(color_string: str) -> Optional[Tuple[int, int, int, float]]:
    """
    Parse a CSS color string and return (R, G, B, A) tuple.
    Returns None if color cannot be parsed.
    """
    if not color_string:
        return None
    
    color_string = color_string.strip().lower()
    
    # Handle 'transparent'
    if color_string == 'transparent':
        return (0, 0, 0, 0.0)
    
    # Handle 'inherit', 'initial', 'unset'
    if color_string in ('inherit', 'initial', 'unset', 'currentcolor'):
        return None
    
    # Named colors
    if color_string in WEB_COLORS:
        r, g, b = WEB_COLORS[color_string]
        return (r, g, b, 1.0)
    
    # Hex colors
    hex_match = re.match(r'^#?([a-f0-9]{3,8})$', color_string)
    if hex_match:
        hex_val = hex_match.group(1)
        if len(hex_val) == 3:
            r = int(hex_val[0] * 2, 16)
            g = int(hex_val[1] * 2, 16)
            b = int(hex_val[2] * 2, 16)
            return (r, g, b, 1.0)
        elif len(hex_val) == 4:
            r = int(hex_val[0] * 2, 16)
            g = int(hex_val[1] * 2, 16)
            b = int(hex_val[2] * 2, 16)
            a = int(hex_val[3] * 2, 16) / 255
            return (r, g, b, a)
        elif len(hex_val) == 6:
            r = int(hex_val[0:2], 16)
            g = int(hex_val[2:4], 16)
            b = int(hex_val[4:6], 16)
            return (r, g, b, 1.0)
        elif len(hex_val) == 8:
            r = int(hex_val[0:2], 16)
            g = int(hex_val[2:4], 16)
            b = int(hex_val[4:6], 16)
            a = int(hex_val[6:8], 16) / 255
            return (r, g, b, a)
    
    # RGB/RGBA
    rgb_match = re.match(r'rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+))?\s*\)', color_string)
    if rgb_match:
        r = int(rgb_match.group(1))
        g = int(rgb_match.group(2))
        b = int(rgb_match.group(3))
        a = float(rgb_match.group(4)) if rgb_match.group(4) else 1.0
        return (min(255, r), min(255, g), min(255, b), min(1.0, a))
    
    # RGB with percentages
    rgb_pct_match = re.match(r'rgba?\s*\(\s*([\d.]+)%\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%\s*(?:,\s*([\d.]+))?\s*\)', color_string)
    if rgb_pct_match:
        r = int(float(rgb_pct_match.group(1)) * 255 / 100)
        g = int(float(rgb_pct_match.group(2)) * 255 / 100)
        b = int(float(rgb_pct_match.group(3)) * 255 / 100)
        a = float(rgb_pct_match.group(4)) if rgb_pct_match.group(4) else 1.0
        return (min(255, r), min(255, g), min(255, b), min(1.0, a))
    
    # HSL/HSLA (convert to RGB)
    hsl_match = re.match(r'hsla?\s*\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%\s*(?:,\s*([\d.]+))?\s*\)', color_string)
    if hsl_match:
        h = float(hsl_match.group(1)) / 360
        s = float(hsl_match.group(2)) / 100
        l = float(hsl_match.group(3)) / 100
        a = float(hsl_match.group(4)) if hsl_match.group(4) else 1.0
        
        r, g, b = hsl_to_rgb(h, s, l)
        return (r, g, b, min(1.0, a))
    
    return None


def hsl_to_rgb(h: float, s: float, l: float) -> Tuple[int, int, int]:
    """Convert HSL to RGB."""
    if s == 0:
        r = g = b = int(l * 255)
    else:
        def hue_to_rgb(p, q, t):
            if t < 0: t += 1
            if t > 1: t -= 1
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p
        
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r = int(hue_to_rgb(p, q, h + 1/3) * 255)
        g = int(hue_to_rgb(p, q, h) * 255)
        b = int(hue_to_rgb(p, q, h - 1/3) * 255)
    
    return (r, g, b)


def get_relative_luminance(r: int, g: int, b: int) -> float:
    """
    Calculate relative luminance according to WCAG 2.1.
    https://www.w3.org/TR/WCAG21/#dfn-relative-luminance
    """
    def adjust(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    
    return 0.2126 * adjust(r) + 0.7152 * adjust(g) + 0.0722 * adjust(b)


def get_contrast_ratio(color1: Tuple[int, int, int], color2: Tuple[int, int, int]) -> float:
    """
    Calculate contrast ratio between two colors.
    https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio
    Returns a value between 1 and 21.
    """
    l1 = get_relative_luminance(*color1)
    l2 = get_relative_luminance(*color2)
    
    lighter = max(l1, l2)
    darker = min(l1, l2)
    
    return (lighter + 0.05) / (darker + 0.05)


def check_contrast_compliance(ratio: float, is_large_text: bool = False, 
                              level: str = "AA") -> bool:
    """
    Check if contrast ratio meets WCAG requirements.
    
    Normal text:
        - AA: 4.5:1
        - AAA: 7:1
    Large text (≥18pt or ≥14pt bold):
        - AA: 3:1
        - AAA: 4.5:1
    """
    if level == "AAA":
        threshold = 4.5 if is_large_text else 7.0
    else:  # AA
        threshold = 3.0 if is_large_text else 4.5
    
    return ratio >= threshold


def is_large_text(font_size: str, font_weight: str = "normal") -> bool:
    """
    Determine if text is considered "large" for WCAG purposes.
    Large text is ≥18pt (24px) or ≥14pt (18.66px) bold.
    """
    # Parse font size
    size_px = parse_font_size(font_size)
    if size_px is None:
        return False
    
    # Check weight
    is_bold = font_weight in ('bold', 'bolder', '700', '800', '900')
    
    # Large text thresholds
    if is_bold:
        return size_px >= 18.66  # 14pt
    else:
        return size_px >= 24  # 18pt


def parse_font_size(font_size: str) -> Optional[float]:
    """Parse CSS font-size and return value in pixels."""
    if not font_size:
        return None
    
    font_size = font_size.strip().lower()
    
    # Pixels
    px_match = re.match(r'([\d.]+)\s*px', font_size)
    if px_match:
        return float(px_match.group(1))
    
    # Points (1pt = 1.333px approximately)
    pt_match = re.match(r'([\d.]+)\s*pt', font_size)
    if pt_match:
        return float(pt_match.group(1)) * 1.333
    
    # Em (assume 16px base)
    em_match = re.match(r'([\d.]+)\s*em', font_size)
    if em_match:
        return float(em_match.group(1)) * 16
    
    # Rem (assume 16px root)
    rem_match = re.match(r'([\d.]+)\s*rem', font_size)
    if rem_match:
        return float(rem_match.group(1)) * 16
    
    # Percentages (assume 16px base)
    pct_match = re.match(r'([\d.]+)\s*%', font_size)
    if pct_match:
        return float(pct_match.group(1)) * 16 / 100
    
    # Named sizes (approximate)
    named_sizes = {
        'xx-small': 9, 'x-small': 10, 'small': 13, 'medium': 16,
        'large': 18, 'x-large': 24, 'xx-large': 32, 'xxx-large': 48
    }
    if font_size in named_sizes:
        return named_sizes[font_size]
    
    return None


def get_css_selector(element) -> str:
    """Generate a CSS selector for a BeautifulSoup element."""
    parts = []
    current = element
    
    while current and current.name:
        if current.name == '[document]':
            break
        
        selector = current.name
        
        # Add ID if present
        if current.get('id'):
            selector += f"#{current['id']}"
            parts.insert(0, selector)
            break  # ID is unique, no need to go further
        
        # Add classes
        classes = current.get('class', [])
        if classes:
            selector += '.' + '.'.join(classes[:2])  # Limit to 2 classes
        
        # Add nth-child if needed to disambiguate
        if current.parent:
            siblings = [s for s in current.parent.children if s.name == current.name]
            if len(siblings) > 1:
                index = siblings.index(current) + 1
                selector += f":nth-child({index})"
        
        parts.insert(0, selector)
        current = current.parent
    
    return ' > '.join(parts) if parts else ''


def get_element_html(element, max_length: int = 200) -> str:
    """Get a string representation of an element for display."""
    html = str(element)
    if len(html) > max_length:
        # Try to get just the opening tag
        match = re.match(r'<[^>]+>', html)
        if match:
            return match.group(0)
        return html[:max_length] + '...'
    return html


def get_text_content(element) -> str:
    """Get the text content of an element."""
    return element.get_text(strip=True) if element else ""


def has_ancestor(element, tag_names: list) -> bool:
    """Check if element has an ancestor with one of the given tag names."""
    if isinstance(tag_names, str):
        tag_names = [tag_names]
    
    parent = element.parent
    while parent:
        if parent.name in tag_names:
            return True
        parent = parent.parent
    return False


def get_accessible_name(element) -> str:
    """
    Get the accessible name of an element.
    Priority: aria-labelledby > aria-label > alt > title > text content
    """
    # aria-labelledby
    labelledby = element.get('aria-labelledby')
    if labelledby:
        # Would need to find referenced elements - simplified for now
        return f"[aria-labelledby: {labelledby}]"
    
    # aria-label
    label = element.get('aria-label')
    if label:
        return label.strip()
    
    # alt (for images)
    alt = element.get('alt')
    if alt:
        return alt.strip()
    
    # title
    title = element.get('title')
    if title:
        return title.strip()
    
    # Text content
    return get_text_content(element)


def extract_inline_styles(element) -> dict:
    """Extract inline styles from an element's style attribute."""
    styles = {}
    style_attr = element.get('style', '')
    
    if not style_attr:
        return styles
    
    for declaration in style_attr.split(';'):
        if ':' in declaration:
            prop, value = declaration.split(':', 1)
            styles[prop.strip().lower()] = value.strip()
    
    return styles
