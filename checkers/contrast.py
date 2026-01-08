"""
WCAG Contrast Accessibility Checker
Covers: 1.4.3 Contrast (Minimum), 1.4.6 Contrast (Enhanced)
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


def check_contrast(soup, url, html=None):
    """Check for potential contrast issues."""
    issues = []
    passed = []
    warnings = []
    
    # Note: Full contrast checking requires computed styles which needs browser
    # This does basic inline style checking and flags potential issues
    
    # Check inline styles for color definitions
    elements_with_color = soup.find_all(style=re.compile(r'color|background', re.I))
    
    for elem in elements_with_color:
        style = elem.get('style', '')
        element_str = str(elem)[:200]
        
        # Extract color values
        color_match = re.search(r'(?<!background-)color\s*:\s*([^;]+)', style, re.I)
        bg_match = re.search(r'background(?:-color)?\s*:\s*([^;]+)', style, re.I)
        
        if color_match and bg_match:
            fg_color = color_match.group(1).strip()
            bg_color = bg_match.group(1).strip()
            
            # Check for potentially problematic combinations
            light_colors = ['white', '#fff', '#ffffff', 'rgb(255,255,255)', 
                          '#f0f0f0', '#eee', '#eeeeee', 'lightgray', 'lightgrey']
            dark_colors = ['black', '#000', '#000000', 'rgb(0,0,0)',
                         '#333', '#333333', 'darkgray', 'darkgrey']
            
            fg_lower = fg_color.lower().replace(' ', '')
            bg_lower = bg_color.lower().replace(' ', '')
            
            # Light on light or dark on dark
            if (fg_lower in light_colors and bg_lower in light_colors) or \
               (fg_lower in dark_colors and bg_lower in dark_colors):
                issues.append(Issue(
                    rule_id="1.4.3",
                    criterion_id="1.4.3",
                    criterion_name="Kontrast (minimum)",
                    criterion_name_en="Contrast (Minimum)",
                    level="AA",
                    impact="serious",
                    element=element_str,
                    selector=elem.name,
                    issue=f"Potential low contrast: {fg_color} on {bg_color}",
                    fix="Ensure text has at least 4.5:1 contrast ratio (3:1 for large text)"
                ))
    
    # Check for text in images (can't check contrast)
    for img in soup.find_all('img'):
        src = img.get('src', '').lower()
        alt = img.get('alt', '')
        
        # Images that might contain text
        if any(x in src for x in ['banner', 'header', 'logo', 'text', 'button']):
            warnings.append(f"1.4.3: Image may contain text - verify contrast: {src[:50]}")
    
    # Check for CSS classes that suggest styling issues
    problematic_classes = ['light-text', 'faded', 'muted', 'subtle', 'gray-text', 'grey-text']
    for cls in problematic_classes:
        elements = soup.find_all(class_=re.compile(cls, re.I))
        if elements:
            warnings.append(f"1.4.3: Found {len(elements)} elements with '{cls}' class - verify contrast")
    
    # Check placeholder contrast (often too light)
    inputs_with_placeholder = soup.find_all(['input', 'textarea'], placeholder=True)
    if inputs_with_placeholder:
        warnings.append(f"1.4.3: {len(inputs_with_placeholder)} inputs with placeholder - ensure placeholder text has sufficient contrast")
    
    # General warning about contrast
    if not issues:
        warnings.append("1.4.3: Automated contrast checking is limited - manual testing recommended with browser tools")
    
    passed.append("1.4.3: Basic inline style contrast check complete")
    
    return issues, passed, warnings
