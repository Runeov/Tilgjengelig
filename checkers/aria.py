"""
WCAG ARIA Checker
Checks proper use of ARIA attributes.
"""

from bs4 import BeautifulSoup
import re

RULE_INFO = {
    "4.1.2": {
        "criterion": "4.1.2",
        "criterion_name": "Navn, rolle, verdi",
        "criterion_name_en": "Name, Role, Value",
        "level": "A",
    }
}

# Valid ARIA roles
VALID_ROLES = {
    # Landmark roles
    'banner', 'complementary', 'contentinfo', 'form', 'main', 'navigation', 'region', 'search',
    # Document structure roles
    'article', 'cell', 'columnheader', 'definition', 'directory', 'document', 'feed', 'figure',
    'group', 'heading', 'img', 'list', 'listitem', 'math', 'none', 'note', 'presentation',
    'row', 'rowgroup', 'rowheader', 'separator', 'table', 'term', 'toolbar', 'tooltip',
    # Widget roles
    'alert', 'alertdialog', 'button', 'checkbox', 'dialog', 'gridcell', 'link', 'log',
    'marquee', 'menuitem', 'menuitemcheckbox', 'menuitemradio', 'option', 'progressbar',
    'radio', 'scrollbar', 'searchbox', 'slider', 'spinbutton', 'status', 'switch', 'tab',
    'tabpanel', 'textbox', 'timer', 'treeitem',
    # Composite roles
    'combobox', 'grid', 'listbox', 'menu', 'menubar', 'radiogroup', 'tablist', 'tree', 'treegrid',
    # Live region roles
    'alert', 'log', 'marquee', 'status', 'timer',
    # Window roles
    'alertdialog', 'dialog',
    # Abstract roles (should not be used)
    'application', 'generic'
}

# Roles that require certain attributes
ROLE_REQUIRED_ATTRS = {
    'checkbox': ['aria-checked'],
    'combobox': ['aria-expanded'],
    'heading': ['aria-level'],
    'meter': ['aria-valuenow'],
    'option': [],
    'radio': ['aria-checked'],
    'scrollbar': ['aria-controls', 'aria-valuenow'],
    'slider': ['aria-valuenow'],
    'spinbutton': ['aria-valuenow'],
    'switch': ['aria-checked'],
}


def check_aria(soup, url, **kwargs):
    """
    Check ARIA usage for proper implementation.
    
    Returns tuple of (issues, passed, warnings).
    """
    issues = []
    passed = []
    warnings = []
    
    rule = RULE_INFO["4.1.2"]
    
    # Check for invalid roles
    elements_with_role = soup.find_all(attrs={'role': True})
    invalid_roles = []
    
    for element in elements_with_role:
        role = element.get('role', '').lower()
        if role and role not in VALID_ROLES:
            invalid_roles.append((element, role))
    
    for element, role in invalid_roles[:5]:
        element_str = str(element)[:200]
        issues.append({
            "rule_id": "4.1.2",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "serious",
            "element": element_str,
            "selector": _get_selector(element),
            "issue": f"Ugyldig ARIA-rolle: '{role}'",
            "fix": "Bruk en gyldig ARIA-rolle fra WAI-ARIA spesifikasjonen"
        })
    
    # Check for missing required attributes
    missing_attrs = []
    for element in elements_with_role:
        role = element.get('role', '').lower()
        if role in ROLE_REQUIRED_ATTRS:
            required = ROLE_REQUIRED_ATTRS[role]
            for attr in required:
                if not element.has_attr(attr):
                    missing_attrs.append((element, role, attr))
    
    for element, role, attr in missing_attrs[:5]:
        element_str = str(element)[:200]
        issues.append({
            "rule_id": "4.1.2",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "serious",
            "element": element_str,
            "selector": _get_selector(element),
            "issue": f"Rolle '{role}' mangler påkrevd attributt: {attr}",
            "fix": f"Legg til {attr} attributtet på elementet"
        })
    
    # Check for aria-hidden on focusable elements
    aria_hidden_focusable = []
    for element in soup.find_all(attrs={'aria-hidden': 'true'}):
        # Check if element or children are focusable
        focusable_tags = ['a', 'button', 'input', 'select', 'textarea']
        if element.name in focusable_tags:
            aria_hidden_focusable.append(element)
        else:
            for child in element.find_all(focusable_tags):
                if not child.has_attr('tabindex') or child.get('tabindex') != '-1':
                    aria_hidden_focusable.append(element)
                    break
    
    for element in aria_hidden_focusable[:3]:
        element_str = str(element)[:200]
        issues.append({
            "rule_id": "4.1.2",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "critical",
            "element": element_str,
            "selector": _get_selector(element),
            "issue": "aria-hidden='true' på element med fokuserbart innhold",
            "fix": "Fjern aria-hidden eller legg til tabindex='-1' på fokuserbare elementer inni"
        })
    
    # Check for aria-labelledby/describedby referencing non-existent IDs
    broken_references = []
    for attr in ['aria-labelledby', 'aria-describedby', 'aria-controls', 'aria-owns']:
        for element in soup.find_all(attrs={attr: True}):
            id_refs = element.get(attr, '').split()
            for id_ref in id_refs:
                if not soup.find(id=id_ref):
                    broken_references.append((element, attr, id_ref))
    
    for element, attr, id_ref in broken_references[:5]:
        element_str = str(element)[:200]
        issues.append({
            "rule_id": "4.1.2",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "serious",
            "element": element_str,
            "selector": _get_selector(element),
            "issue": f"{attr} refererer til ikke-eksisterende ID: '{id_ref}'",
            "fix": f"Sørg for at element med id='{id_ref}' finnes på siden"
        })
    
    # Check for redundant roles on semantic elements
    redundant_roles = {
        'a': ['link'],
        'article': ['article'],
        'aside': ['complementary'],
        'button': ['button'],
        'footer': ['contentinfo'],
        'form': ['form'],
        'h1': ['heading'], 'h2': ['heading'], 'h3': ['heading'],
        'h4': ['heading'], 'h5': ['heading'], 'h6': ['heading'],
        'header': ['banner'],
        'img': ['img'],
        'input': ['textbox', 'checkbox', 'radio', 'button'],
        'li': ['listitem'],
        'main': ['main'],
        'nav': ['navigation'],
        'ol': ['list'],
        'select': ['listbox'],
        'table': ['table'],
        'textarea': ['textbox'],
        'ul': ['list'],
    }
    
    redundant_found = []
    for element in elements_with_role:
        role = element.get('role', '').lower()
        tag = element.name
        if tag in redundant_roles and role in redundant_roles[tag]:
            redundant_found.append((element, tag, role))
    
    for element, tag, role in redundant_found[:3]:
        element_str = str(element)[:150]
        warnings.append({
            "rule_id": "4.1.2",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "minor",
            "element": element_str,
            "selector": _get_selector(element),
            "issue": f"Overflødig rolle '{role}' på <{tag}> - dette er allerede implisitt",
            "fix": f"Fjern role='{role}' attributtet - <{tag}> har denne rollen automatisk"
        })
    
    # Summary
    total_issues = len(invalid_roles) + len(missing_attrs) + len(aria_hidden_focusable) + len(broken_references)
    if total_issues == 0 and len(elements_with_role) > 0:
        passed.append({
            "rule_id": "4.1.2",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "message": f"ARIA-attributter brukt korrekt på {len(elements_with_role)} elementer"
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
