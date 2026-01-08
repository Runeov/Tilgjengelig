"""
WCAG ARIA Accessibility Checker
Covers: 4.1.2 Name, Role, Value and ARIA best practices
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


# Valid ARIA roles
VALID_ROLES = {
    # Landmark roles
    'banner', 'complementary', 'contentinfo', 'form', 'main', 'navigation', 'region', 'search',
    # Widget roles
    'alert', 'alertdialog', 'button', 'checkbox', 'dialog', 'gridcell', 'link', 'log',
    'marquee', 'menuitem', 'menuitemcheckbox', 'menuitemradio', 'option', 'progressbar',
    'radio', 'scrollbar', 'searchbox', 'slider', 'spinbutton', 'status', 'switch', 'tab',
    'tabpanel', 'textbox', 'timer', 'tooltip', 'treeitem',
    # Composite widget roles
    'combobox', 'grid', 'listbox', 'menu', 'menubar', 'radiogroup', 'tablist', 'tree', 'treegrid',
    # Document structure roles
    'application', 'article', 'cell', 'columnheader', 'definition', 'directory', 'document',
    'feed', 'figure', 'group', 'heading', 'img', 'list', 'listitem', 'math', 'none', 'note',
    'presentation', 'row', 'rowgroup', 'rowheader', 'separator', 'table', 'term', 'toolbar',
    # Abstract roles (should not be used directly)
}

ABSTRACT_ROLES = {
    'command', 'composite', 'input', 'landmark', 'range', 'roletype', 'section',
    'sectionhead', 'select', 'structure', 'widget', 'window'
}

# Roles that require specific attributes
ROLE_REQUIRED_ATTRS = {
    'checkbox': ['aria-checked'],
    'combobox': ['aria-expanded'],
    'heading': ['aria-level'],
    'meter': ['aria-valuenow'],
    'option': ['aria-selected'],
    'radio': ['aria-checked'],
    'scrollbar': ['aria-controls', 'aria-valuenow'],
    'searchbox': [],
    'slider': ['aria-valuenow'],
    'spinbutton': ['aria-valuenow'],
    'switch': ['aria-checked'],
    'tab': ['aria-selected'],
    'tabpanel': [],
    'textbox': [],
    'treeitem': [],
}

# Roles that require a name
ROLES_REQUIRING_NAME = {
    'alertdialog', 'dialog', 'form', 'region', 'article', 'figure',
    'img', 'table', 'navigation', 'complementary'
}


def check_aria(soup, url, html=None):
    """Check ARIA usage for accessibility issues."""
    issues = []
    passed = []
    warnings = []
    
    # Check all elements with role attribute
    elements_with_role = soup.find_all(role=True)
    
    for elem in elements_with_role:
        role = elem.get('role', '').lower()
        element_str = str(elem)[:200]
        
        # Check for valid role
        if role not in VALID_ROLES:
            if role in ABSTRACT_ROLES:
                issues.append(Issue(
                    rule_id="4.1.2",
                    criterion_id="4.1.2",
                    criterion_name="Navn, rolle, verdi",
                    criterion_name_en="Name, Role, Value",
                    level="A",
                    impact="serious",
                    element=element_str,
                    selector=f'[role="{role}"]',
                    issue=f"Abstract role '{role}' should not be used",
                    fix="Use a concrete role instead of abstract roles"
                ))
            else:
                issues.append(Issue(
                    rule_id="4.1.2",
                    criterion_id="4.1.2",
                    criterion_name="Navn, rolle, verdi",
                    criterion_name_en="Name, Role, Value",
                    level="A",
                    impact="serious",
                    element=element_str,
                    selector=f'[role="{role}"]',
                    issue=f"Invalid ARIA role: '{role}'",
                    fix="Use a valid ARIA role from the specification"
                ))
            continue
        
        # Check for required attributes
        if role in ROLE_REQUIRED_ATTRS:
            required = ROLE_REQUIRED_ATTRS[role]
            for attr in required:
                if not elem.get(attr):
                    issues.append(Issue(
                        rule_id="4.1.2",
                        criterion_id="4.1.2",
                        criterion_name="Navn, rolle, verdi",
                        criterion_name_en="Name, Role, Value",
                        level="A",
                        impact="serious",
                        element=element_str,
                        selector=f'[role="{role}"]',
                        issue=f"Role '{role}' requires {attr} attribute",
                        fix=f"Add {attr} attribute to element with role='{role}'"
                    ))
        
        # Check roles that need accessible name
        if role in ROLES_REQUIRING_NAME:
            has_name = (elem.get('aria-label') or 
                       elem.get('aria-labelledby') or
                       elem.get('title') or
                       elem.find('legend') or
                       elem.find('figcaption'))
            
            if not has_name:
                issues.append(Issue(
                    rule_id="4.1.2",
                    criterion_id="4.1.2",
                    criterion_name="Navn, rolle, verdi",
                    criterion_name_en="Name, Role, Value",
                    level="A",
                    impact="moderate",
                    element=element_str,
                    selector=f'[role="{role}"]',
                    issue=f"Element with role='{role}' needs an accessible name",
                    fix="Add aria-label or aria-labelledby attribute"
                ))
        
        passed.append(f"4.1.2: Valid role found: {role}")
    
    # Check aria-labelledby references
    labelledby_elements = soup.find_all(attrs={'aria-labelledby': True})
    for elem in labelledby_elements:
        ref_id = elem.get('aria-labelledby')
        ref_ids = ref_id.split()
        
        for rid in ref_ids:
            ref = soup.find(id=rid)
            if not ref:
                issues.append(Issue(
                    rule_id="4.1.2",
                    criterion_id="4.1.2",
                    criterion_name="Navn, rolle, verdi",
                    criterion_name_en="Name, Role, Value",
                    level="A",
                    impact="serious",
                    element=str(elem)[:200],
                    selector=f'[aria-labelledby="{ref_id}"]',
                    issue=f"aria-labelledby references non-existent ID: '{rid}'",
                    fix="Ensure the referenced ID exists on the page"
                ))
    
    # Check aria-describedby references
    describedby_elements = soup.find_all(attrs={'aria-describedby': True})
    for elem in describedby_elements:
        ref_id = elem.get('aria-describedby')
        ref_ids = ref_id.split()
        
        for rid in ref_ids:
            ref = soup.find(id=rid)
            if not ref:
                issues.append(Issue(
                    rule_id="4.1.2",
                    criterion_id="4.1.2",
                    criterion_name="Navn, rolle, verdi",
                    criterion_name_en="Name, Role, Value",
                    level="A",
                    impact="moderate",
                    element=str(elem)[:200],
                    selector=f'[aria-describedby="{ref_id}"]',
                    issue=f"aria-describedby references non-existent ID: '{rid}'",
                    fix="Ensure the referenced ID exists on the page"
                ))
    
    # Check aria-controls references
    controls_elements = soup.find_all(attrs={'aria-controls': True})
    for elem in controls_elements:
        ref_id = elem.get('aria-controls')
        ref_ids = ref_id.split()
        
        for rid in ref_ids:
            ref = soup.find(id=rid)
            if not ref:
                warnings.append(f"4.1.2: aria-controls references '{rid}' which may be dynamically added")
    
    # Check for aria-hidden on focusable elements
    aria_hidden = soup.find_all(attrs={'aria-hidden': 'true'})
    for elem in aria_hidden:
        # Check if element or children are focusable
        focusable = elem.find_all(['a', 'button', 'input', 'select', 'textarea'])
        focusable += [elem] if elem.name in ['a', 'button', 'input', 'select', 'textarea'] else []
        
        for foc in focusable:
            if foc.get('tabindex') != '-1':
                issues.append(Issue(
                    rule_id="4.1.2",
                    criterion_id="4.1.2",
                    criterion_name="Navn, rolle, verdi",
                    criterion_name_en="Name, Role, Value",
                    level="A",
                    impact="serious",
                    element=str(foc)[:200],
                    selector=f'{foc.name}[aria-hidden="true"]',
                    issue="Focusable element is inside aria-hidden container",
                    fix="Remove from tab order with tabindex='-1' or remove aria-hidden"
                ))
    
    # Check for conflicting roles on native elements
    native_role_conflicts = [
        ('button', ['link', 'checkbox', 'menuitem']),
        ('a', ['button']),  # OK if href is missing
        ('input', ['link']),
        ('select', ['button', 'link']),
    ]
    
    for tag, bad_roles in native_role_conflicts:
        for elem in soup.find_all(tag, role=True):
            role = elem.get('role', '').lower()
            if role in bad_roles:
                # Exception: anchor without href can be button
                if tag == 'a' and not elem.get('href') and role == 'button':
                    continue
                
                issues.append(Issue(
                    rule_id="4.1.2",
                    criterion_id="4.1.2",
                    criterion_name="Navn, rolle, verdi",
                    criterion_name_en="Name, Role, Value",
                    level="A",
                    impact="moderate",
                    element=str(elem)[:200],
                    selector=f'{tag}[role="{role}"]',
                    issue=f"<{tag}> element has conflicting role='{role}'",
                    fix=f"Use native <{tag}> semantics or change to appropriate element"
                ))
    
    # Check for empty aria-label
    aria_labels = soup.find_all(attrs={'aria-label': True})
    for elem in aria_labels:
        label = elem.get('aria-label', '').strip()
        if not label:
            issues.append(Issue(
                rule_id="4.1.2",
                criterion_id="4.1.2",
                criterion_name="Navn, rolle, verdi",
                criterion_name_en="Name, Role, Value",
                level="A",
                impact="serious",
                element=str(elem)[:200],
                selector='[aria-label=""]',
                issue="Element has empty aria-label",
                fix="Provide descriptive text in aria-label or remove if not needed"
            ))
    
    return issues, passed, warnings
