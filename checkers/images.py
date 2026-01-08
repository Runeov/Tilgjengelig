"""
WCAG 1.1.1 Image Checker
Checks that images have appropriate text alternatives.
"""

from bs4 import BeautifulSoup

RULE_INFO = {
    "1.1.1a": {
        "criterion": "1.1.1",
        "criterion_name": "Ikke-tekstlig innhold",
        "criterion_name_en": "Non-text Content",
        "level": "A",
    },
    "1.1.1b": {
        "criterion": "1.1.1",
        "criterion_name": "Ikke-tekstlig innhold",
        "criterion_name_en": "Non-text Content",
        "level": "A",
    },
}


def check_images(soup, url, **kwargs):
    """
    Check images for proper text alternatives.
    
    Returns tuple of (issues, passed, warnings).
    """
    issues = []
    passed = []
    warnings = []
    
    rule = RULE_INFO["1.1.1a"]
    
    # Find all images
    images = soup.find_all('img')
    
    missing_alt = []
    empty_alt = []
    decorative = []
    has_alt = []
    
    for img in images:
        # Check for alt attribute
        if not img.has_attr('alt'):
            missing_alt.append(img)
        elif img['alt'].strip() == '':
            # Empty alt is valid for decorative images
            # Check if it seems decorative (in link, has aria-hidden, etc.)
            parent_link = img.find_parent('a')
            is_decorative = (
                img.get('aria-hidden') == 'true' or
                img.get('role') == 'presentation' or
                'decorative' in img.get('class', []) or
                'icon' in img.get('class', [])
            )
            
            if parent_link and parent_link.get_text(strip=True):
                # Image in link with text - empty alt is fine
                decorative.append(img)
            elif is_decorative:
                decorative.append(img)
            else:
                empty_alt.append(img)
        else:
            has_alt.append(img)
    
    # Report missing alt
    for img in missing_alt[:10]:
        src = img.get('src', 'ukjent')[:100]
        element_str = str(img)[:200]
        issues.append({
            "rule_id": "1.1.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "critical",
            "element": element_str,
            "selector": _get_selector(img),
            "issue": f"Bilde mangler alt-attributt: {src}",
            "fix": "Legg til beskrivende alt-tekst, eller alt=\"\" for dekorative bilder"
        })
    
    # Report suspicious empty alt
    for img in empty_alt[:5]:
        src = img.get('src', 'ukjent')[:100]
        element_str = str(img)[:200]
        warnings.append({
            "rule_id": "1.1.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "moderate",
            "element": element_str,
            "selector": _get_selector(img),
            "issue": f"Bilde har tom alt-tekst - verifiser at det er dekorativt: {src}",
            "fix": "Hvis bildet formidler informasjon, legg til beskrivende alt-tekst"
        })
    
    # Check linked images
    rule_b = RULE_INFO["1.1.1b"]
    linked_images = soup.find_all('a')
    
    for link in linked_images:
        img = link.find('img')
        if img:
            link_text = link.get_text(strip=True)
            img_alt = img.get('alt', '').strip()
            aria_label = link.get('aria-label', '').strip()
            
            # If no link text and no alt and no aria-label, it's a problem
            if not link_text and not img_alt and not aria_label:
                element_str = str(link)[:200]
                issues.append({
                    "rule_id": "1.1.1b",
                    "criterion_id": rule_b["criterion"],
                    "criterion_name": rule_b["criterion_name"],
                    "criterion_name_en": rule_b["criterion_name_en"],
                    "level": rule_b["level"],
                    "impact": "critical",
                    "element": element_str,
                    "selector": _get_selector(link),
                    "issue": "Bildlenke mangler tekstalternativ",
                    "fix": "Legg til alt-tekst på bildet eller aria-label på lenken"
                })
    
    # Summary
    total_images = len(images)
    if total_images > 0:
        if len(missing_alt) == 0 and len(empty_alt) == 0:
            passed.append({
                "rule_id": "1.1.1a",
                "criterion_id": rule["criterion"],
                "criterion_name": rule["criterion_name"],
                "message": f"Alle {total_images} bilder har alt-attributt"
            })
    
    if len(missing_alt) > 10:
        warnings.append({
            "rule_id": "1.1.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "moderate",
            "element": "Multiple images",
            "selector": "",
            "issue": f"Fant {len(missing_alt)} bilder uten alt-attributt (viser kun de første 10)",
            "fix": "Gjennomgå alle bilder og legg til passende tekstalternativer"
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
