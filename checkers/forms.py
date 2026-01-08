"""
WCAG 3.3.2 Forms Checker
Checks form elements for labels and instructions.
"""

from bs4 import BeautifulSoup

RULE_INFO = {
    "3.3.2a": {
        "criterion": "3.3.2",
        "criterion_name": "Ledetekster eller instruksjoner",
        "criterion_name_en": "Labels or Instructions",
        "level": "A",
    },
    "1.3.1e": {
        "criterion": "1.3.1",
        "criterion_name": "Informasjon og relasjoner",
        "criterion_name_en": "Info and Relationships",
        "level": "A",
    }
}


def get_label_for_input(element, soup):
    """Find the associated label for an input element."""
    # Check for label with for attribute
    element_id = element.get('id')
    if element_id:
        label = soup.find('label', attrs={'for': element_id})
        if label:
            return label.get_text(strip=True)
    
    # Check for wrapping label
    parent_label = element.find_parent('label')
    if parent_label:
        return parent_label.get_text(strip=True)
    
    # Check aria-label
    aria_label = element.get('aria-label', '').strip()
    if aria_label:
        return aria_label
    
    # Check aria-labelledby
    labelledby = element.get('aria-labelledby')
    if labelledby:
        labels = []
        for id_ref in labelledby.split():
            ref_element = soup.find(id=id_ref)
            if ref_element:
                labels.append(ref_element.get_text(strip=True))
        if labels:
            return ' '.join(labels)
    
    return None


def check_forms(soup, url, **kwargs):
    """
    Check form elements for proper labels and instructions.
    
    Returns tuple of (issues, passed, warnings).
    """
    issues = []
    passed = []
    warnings = []
    
    rule = RULE_INFO["3.3.2a"]
    
    # Find all form inputs (excluding hidden, submit, button, reset)
    inputs = soup.find_all('input', type=lambda x: x not in ['hidden', 'submit', 'button', 'reset', 'image'])
    selects = soup.find_all('select')
    textareas = soup.find_all('textarea')
    
    all_inputs = list(inputs) + list(selects) + list(textareas)
    
    missing_labels = []
    placeholder_only = []
    has_labels = 0
    
    for element in all_inputs:
        label = get_label_for_input(element, soup)
        placeholder = element.get('placeholder', '').strip()
        
        if label:
            has_labels += 1
        elif placeholder:
            placeholder_only.append(element)
        else:
            missing_labels.append(element)
    
    # Report missing labels
    for element in missing_labels[:5]:
        element_type = element.get('type', element.name)
        element_name = element.get('name', 'ukjent')
        element_str = str(element)[:200]
        
        issues.append({
            "rule_id": "3.3.2a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "critical",
            "element": element_str,
            "selector": _get_selector(element),
            "issue": f"Skjemafelt ({element_type}, name='{element_name}') mangler ledetekst",
            "fix": "Legg til <label> element med for-attributt, eller bruk aria-label"
        })
    
    # Report placeholder-only (warning - not sufficient)
    for element in placeholder_only[:5]:
        element_type = element.get('type', element.name)
        placeholder = element.get('placeholder', '')
        element_str = str(element)[:200]
        
        warnings.append({
            "rule_id": "3.3.2a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "serious",
            "element": element_str,
            "selector": _get_selector(element),
            "issue": f"Skjemafelt ({element_type}) bruker kun placeholder ('{placeholder}') som ledetekst",
            "fix": "Placeholder forsvinner når brukeren skriver. Legg til synlig <label>."
        })
    
    # Check for required fields without indication
    required_inputs = soup.find_all(['input', 'select', 'textarea'], required=True)
    required_without_aria = []
    
    for element in required_inputs:
        aria_required = element.get('aria-required')
        if not aria_required:
            # Check if label has asterisk or "påkrevd/required" text
            label = get_label_for_input(element, soup)
            if label and ('*' in label or 'påkrevd' in label.lower() or 'required' in label.lower()):
                continue
            required_without_aria.append(element)
    
    for element in required_without_aria[:3]:
        element_str = str(element)[:200]
        warnings.append({
            "rule_id": "1.3.1e",
            "criterion_id": "1.3.1",
            "criterion_name": "Informasjon og relasjoner",
            "criterion_name_en": "Info and Relationships",
            "level": "A",
            "impact": "moderate",
            "element": element_str,
            "selector": _get_selector(element),
            "issue": "Påkrevd felt mangler visuell indikator i ledeteksten",
            "fix": "Legg til asterisk (*) eller 'påkrevd' i ledeteksten for påkrevde felt"
        })
    
    # Summary
    if len(all_inputs) > 0:
        if len(missing_labels) == 0 and len(placeholder_only) == 0:
            passed.append({
                "rule_id": "3.3.2a",
                "criterion_id": rule["criterion"],
                "criterion_name": rule["criterion_name"],
                "message": f"Alle {len(all_inputs)} skjemafelt har ledetekster"
            })
    
    if len(missing_labels) > 5 or len(placeholder_only) > 5:
        warnings.append({
            "rule_id": "3.3.2a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "moderate",
            "element": "Multiple form elements",
            "selector": "",
            "issue": f"Fant {len(missing_labels)} felt uten ledetekst og {len(placeholder_only)} med kun placeholder",
            "fix": "Gjennomgå alle skjemafelt og legg til passende ledetekster"
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
    elif element.get('name'):
        parts[-1] += f"[name='{element['name']}']"
    
    return ' > '.join(parts[-4:])
