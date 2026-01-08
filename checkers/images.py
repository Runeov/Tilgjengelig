"""
WCAG Image Accessibility Checker
Covers: 1.1.1 Non-text Content
"""

from dataclasses import dataclass


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


def check_images(soup, url, html=None):
    """Check images for accessibility issues."""
    issues = []
    passed = []
    warnings = []
    
    # Check all img elements
    for img in soup.find_all('img'):
        alt = img.get('alt')
        src = img.get('src', '')
        element_str = str(img)[:200]
        
        # Check for missing alt attribute
        if alt is None:
            issues.append(Issue(
                rule_id="1.1.1a",
                criterion_id="1.1.1",
                criterion_name="Ikke-tekstlig innhold",
                criterion_name_en="Non-text Content",
                level="A",
                impact="critical",
                element=element_str,
                selector=f'img[src="{src[:50]}"]',
                issue="Image is missing alt attribute",
                fix="Add alt attribute describing the image, or alt='' if decorative"
            ))
        elif alt == '' and not _is_decorative(img):
            # Empty alt on potentially meaningful image
            parent = img.parent
            if parent and parent.name == 'a':
                # Image inside link with empty alt - may be OK if link has other text
                link_text = parent.get_text(strip=True)
                if not link_text:
                    issues.append(Issue(
                        rule_id="1.1.1b",
                        criterion_id="1.1.1",
                        criterion_name="Ikke-tekstlig innhold",
                        criterion_name_en="Non-text Content",
                        level="A",
                        impact="critical",
                        element=element_str,
                        selector=f'img[src="{src[:50]}"]',
                        issue="Linked image has empty alt and link has no other text",
                        fix="Add descriptive alt text to the image"
                    ))
                else:
                    passed.append(f"1.1.1b: Linked image with alt='' has link text: {link_text[:30]}")
            else:
                passed.append(f"1.1.1a: Image has alt='' (decorative): {src[:50]}")
        else:
            passed.append(f"1.1.1a: Image has alt text: {(alt or '')[:30]}")
    
    # Check SVG elements
    for svg in soup.find_all('svg'):
        has_title = svg.find('title')
        aria_label = svg.get('aria-label')
        aria_hidden = svg.get('aria-hidden')
        role = svg.get('role')
        element_str = str(svg)[:200]
        
        if aria_hidden == 'true' or role == 'presentation':
            passed.append("1.1.1: SVG marked as decorative")
        elif not has_title and not aria_label:
            issues.append(Issue(
                rule_id="1.1.1a",
                criterion_id="1.1.1",
                criterion_name="Ikke-tekstlig innhold",
                criterion_name_en="Non-text Content",
                level="A",
                impact="serious",
                element=element_str,
                selector="svg",
                issue="SVG is missing accessible name",
                fix="Add <title> element inside SVG, or aria-label attribute. Use role='presentation' if decorative"
            ))
        else:
            passed.append("1.1.1: SVG has accessible name")
    
    # Check canvas elements
    for canvas in soup.find_all('canvas'):
        aria_label = canvas.get('aria-label')
        inner_text = canvas.get_text(strip=True)
        element_str = str(canvas)[:200]
        
        if not aria_label and not inner_text:
            issues.append(Issue(
                rule_id="1.1.1a",
                criterion_id="1.1.1",
                criterion_name="Ikke-tekstlig innhold",
                criterion_name_en="Non-text Content",
                level="A",
                impact="serious",
                element=element_str,
                selector="canvas",
                issue="Canvas element has no text alternative",
                fix="Add aria-label or fallback text content inside canvas"
            ))
    
    # Check image maps
    for map_elem in soup.find_all('map'):
        for area in map_elem.find_all('area'):
            alt = area.get('alt')
            href = area.get('href', '')
            
            if not alt:
                issues.append(Issue(
                    rule_id="1.1.1c",
                    criterion_id="1.1.1",
                    criterion_name="Ikke-tekstlig innhold",
                    criterion_name_en="Non-text Content",
                    level="A",
                    impact="critical",
                    element=str(area)[:200],
                    selector=f'area[href="{href[:30]}"]',
                    issue="Image map area missing alt text",
                    fix="Add alt attribute describing the clickable area"
                ))
    
    return issues, passed, warnings


def _is_decorative(img):
    """Check if an image is likely decorative."""
    # Check common decorative patterns
    src = img.get('src', '').lower()
    classes = ' '.join(img.get('class', [])).lower()
    
    decorative_patterns = [
        'spacer', 'blank', 'pixel', 'transparent',
        'decoration', 'decorative', 'ornament',
        'bullet', 'separator', 'divider'
    ]
    
    for pattern in decorative_patterns:
        if pattern in src or pattern in classes:
            return True
    
    # Check for role="presentation" or aria-hidden
    if img.get('role') == 'presentation':
        return True
    if img.get('aria-hidden') == 'true':
        return True
    
    return False
