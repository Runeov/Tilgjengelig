"""
WCAG Non-text Contrast Accessibility Checker
Covers: 1.4.11 Non-text Contrast
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


def check_non_text_contrast(soup, url, html=None):
    """Check non-text elements for sufficient contrast (3:1 minimum)."""
    issues = []
    passed = []
    warnings = []
    
    # Note: Full contrast checking requires computed styles
    # This performs heuristic checks for common issues
    
    # Check form inputs for visible borders
    inputs = soup.find_all(['input', 'select', 'textarea'])
    for inp in inputs:
        inp_type = inp.get('type', 'text')
        if inp_type == 'hidden':
            continue
        
        style = inp.get('style', '')
        classes = ' '.join(inp.get('class', []))
        element_str = str(inp)[:200]
        
        # Check for border: none or border: 0
        if re.search(r'border\s*:\s*(none|0)', style, re.I):
            # Check if there's a background or other visual indicator
            has_bg = 'background' in style.lower()
            has_outline = 'outline' in style.lower()
            has_shadow = 'shadow' in style.lower()
            
            if not (has_bg or has_outline or has_shadow):
                issues.append(Issue(
                    rule_id="1.4.11",
                    criterion_id="1.4.11",
                    criterion_name="Kontrast for ikke-tekstlig innhold",
                    criterion_name_en="Non-text Contrast",
                    level="AA",
                    impact="serious",
                    element=element_str,
                    selector=inp.name,
                    issue="Form input has no visible border",
                    fix="Ensure input has visible boundary with 3:1 contrast ratio"
                ))
    
    # Check buttons for visibility
    buttons = soup.find_all('button')
    for btn in buttons:
        style = btn.get('style', '')
        element_str = str(btn)[:200]
        
        # Transparent or no background buttons need good border/text contrast
        if 'transparent' in style.lower() or 'background: none' in style.lower():
            if 'border: none' in style.lower() or 'border: 0' in style.lower():
                warnings.append("1.4.11: Button may lack sufficient visual boundary")
    
    # Check for icon buttons (SVG/icon fonts)
    icon_buttons = soup.find_all('button')
    for btn in icon_buttons:
        svg = btn.find('svg')
        icon = btn.find('i', class_=re.compile(r'fa-|icon-|material'))
        text = btn.get_text(strip=True)
        
        if (svg or icon) and not text:
            # Icon-only button - need to verify icon contrast
            if svg:
                fill = svg.get('fill', '')
                if fill.lower() in ['none', 'transparent']:
                    warnings.append("1.4.11: Icon button SVG may lack sufficient contrast")
            warnings.append("1.4.11: Icon-only button found - verify icon has 3:1 contrast")
    
    # Check focus indicators
    if html:
        # Check for focus styles that might be too subtle
        if ':focus' in html:
            if 'outline: none' in html or 'outline:none' in html:
                if 'outline: ' not in html.replace('outline: none', '').replace('outline:none', ''):
                    warnings.append("1.4.11: Focus styles may remove outline without replacement")
    
    # Check custom checkboxes/radios
    custom_controls = soup.find_all(role=['checkbox', 'radio', 'switch'])
    for ctrl in custom_controls:
        warnings.append("1.4.11: Custom form control found - verify visual indicator has 3:1 contrast")
    
    # Check progress bars and sliders
    progress = soup.find_all(['progress', 'meter'])
    sliders = soup.find_all(role='slider')
    
    for elem in progress + sliders:
        warnings.append(f"1.4.11: {elem.name or 'Slider'} found - verify filled/unfilled areas have 3:1 contrast")
    
    # Check charts and graphs
    charts = soup.find_all(['canvas', 'svg'])
    for chart in charts:
        classes = ' '.join(chart.get('class', []))
        if any(x in classes.lower() for x in ['chart', 'graph', 'plot', 'diagram']):
            warnings.append("1.4.11: Chart/graph found - verify data series have 3:1 contrast against background")
    
    # Check for thin lines (may be hard to see)
    if html:
        thin_line_patterns = [
            r'border(-\w+)?:\s*1px\s+solid\s+(#[a-fA-F0-9]{3,6}|rgb)',
            r'stroke-width:\s*1',
        ]
        for pattern in thin_line_patterns:
            if re.search(pattern, html, re.I):
                warnings.append("1.4.11: Thin borders found - verify 3:1 contrast ratio")
                break
    
    # Check links that look like buttons
    button_links = soup.find_all('a', class_=re.compile(r'btn|button', re.I))
    for link in button_links:
        style = link.get('style', '')
        if 'background' not in style.lower():
            warnings.append("1.4.11: Link styled as button - verify boundary contrast")
    
    # Summary
    if not issues:
        passed.append("1.4.11: Basic non-text contrast check complete (manual verification recommended)")
    
    return issues, passed, warnings
