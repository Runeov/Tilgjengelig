"""
WCAG Keyboard Accessibility Checker
Covers: 2.1.1 Keyboard, 2.1.2 No Keyboard Trap, 2.4.3 Focus Order, 2.4.7 Focus Visible
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


def check_keyboard(soup, url, html=None):
    """Check for keyboard accessibility issues."""
    issues = []
    passed = []
    warnings = []
    
    # Check for elements with onclick but no keyboard equivalent
    onclick_elements = soup.find_all(onclick=True)
    for elem in onclick_elements:
        tag = elem.name
        element_str = str(elem)[:200]
        
        # These elements are naturally keyboard accessible
        if tag in ['a', 'button', 'input', 'select', 'textarea']:
            # Check if anchor has href
            if tag == 'a' and not elem.get('href'):
                issues.append(Issue(
                    rule_id="2.1.1",
                    criterion_id="2.1.1",
                    criterion_name="Tastatur",
                    criterion_name_en="Keyboard",
                    level="A",
                    impact="critical",
                    element=element_str,
                    selector="a[onclick]",
                    issue="Link with onclick but no href is not keyboard accessible",
                    fix="Add href attribute or use a button element"
                ))
            else:
                passed.append(f"2.1.1: {tag} with onclick is keyboard accessible")
            continue
        
        # Non-interactive elements with onclick
        has_tabindex = elem.get('tabindex') is not None
        has_role = elem.get('role') in ['button', 'link', 'menuitem', 'tab']
        has_keydown = elem.get('onkeydown') or elem.get('onkeypress') or elem.get('onkeyup')
        
        if not has_tabindex:
            issues.append(Issue(
                rule_id="2.1.1",
                criterion_id="2.1.1",
                criterion_name="Tastatur",
                criterion_name_en="Keyboard",
                level="A",
                impact="critical",
                element=element_str,
                selector=f"{tag}[onclick]",
                issue=f"<{tag}> with onclick has no tabindex - not keyboard focusable",
                fix="Add tabindex='0' to make element focusable, or use a button/link"
            ))
        elif not has_keydown:
            issues.append(Issue(
                rule_id="2.1.1",
                criterion_id="2.1.1",
                criterion_name="Tastatur",
                criterion_name_en="Keyboard",
                level="A",
                impact="critical",
                element=element_str,
                selector=f"{tag}[onclick]",
                issue=f"<{tag}> with onclick has no keyboard handler",
                fix="Add onkeydown handler for Enter/Space, or use a button element"
            ))
        else:
            passed.append(f"2.1.1: {tag} with onclick has keyboard support")
    
    # Check for positive tabindex (disrupts natural order)
    positive_tabindex = soup.find_all(tabindex=re.compile(r'^[1-9]'))
    for elem in positive_tabindex:
        tabindex = elem.get('tabindex')
        issues.append(Issue(
            rule_id="2.4.3",
            criterion_id="2.4.3",
            criterion_name="Fokusrekkefølge",
            criterion_name_en="Focus Order",
            level="A",
            impact="serious",
            element=str(elem)[:200],
            selector=f'[tabindex="{tabindex}"]',
            issue=f"Positive tabindex ({tabindex}) disrupts natural focus order",
            fix="Use tabindex='0' for focusable elements or '-1' for programmatic focus only"
        ))
    
    # Check for tabindex="-1" on interactive elements
    negative_tabindex = soup.find_all(['a', 'button', 'input', 'select', 'textarea'], 
                                       tabindex='-1')
    for elem in negative_tabindex:
        if elem.name == 'a' and elem.get('href'):
            warnings.append(f"2.4.3: Link with tabindex='-1' - may be intentionally unfocusable")
        elif elem.name in ['button', 'input', 'select', 'textarea']:
            issues.append(Issue(
                rule_id="2.1.1",
                criterion_id="2.1.1",
                criterion_name="Tastatur",
                criterion_name_en="Keyboard",
                level="A",
                impact="serious",
                element=str(elem)[:200],
                selector=f'{elem.name}[tabindex="-1"]',
                issue=f"Interactive {elem.name} has tabindex='-1' - not keyboard accessible",
                fix="Remove tabindex='-1' unless element is in an inactive state"
            ))
    
    # Check for outline:none or outline:0 (removes focus indicator)
    outline_none = soup.find_all(style=re.compile(r'outline\s*:\s*(none|0)', re.I))
    for elem in outline_none:
        issues.append(Issue(
            rule_id="2.4.7",
            criterion_id="2.4.7",
            criterion_name="Synlig fokus",
            criterion_name_en="Focus Visible",
            level="AA",
            impact="serious",
            element=str(elem)[:200],
            selector=elem.name,
            issue="Element has outline:none which may hide focus indicator",
            fix="Provide alternative focus styling if removing default outline"
        ))
    
    # Check for accesskey (can cause issues)
    accesskey_elements = soup.find_all(accesskey=True)
    for elem in accesskey_elements:
        key = elem.get('accesskey')
        warnings.append(f"2.1.1: Element uses accesskey='{key}' - may conflict with browser/AT shortcuts")
    
    # Check for mouse-only events without keyboard equivalents
    mouse_events = ['onmouseover', 'onmouseout', 'onmouseenter', 'onmouseleave', 'ondblclick']
    keyboard_equivalents = ['onfocus', 'onblur', 'onkeydown', 'onkeypress', 'onkeyup']
    
    for event in mouse_events:
        elements = soup.find_all(attrs={event: True})
        for elem in elements:
            has_keyboard = any(elem.get(ke) for ke in keyboard_equivalents)
            if not has_keyboard:
                issues.append(Issue(
                    rule_id="2.1.1",
                    criterion_id="2.1.1",
                    criterion_name="Tastatur",
                    criterion_name_en="Keyboard",
                    level="A",
                    impact="serious",
                    element=str(elem)[:200],
                    selector=f'[{event}]',
                    issue=f"Element has {event} without keyboard equivalent",
                    fix=f"Add keyboard event handlers (onfocus, onblur, onkeydown) for equivalent functionality"
                ))
    
    # Check for scroll hijacking (potential keyboard trap)
    if html:
        if 'scroll-behavior: smooth' in html or 'scrollIntoView' in html:
            warnings.append("2.1.2: Page may use scroll behavior - verify no keyboard traps exist")
    
    return issues, passed, warnings
