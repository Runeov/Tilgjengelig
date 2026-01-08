"""
WCAG Name, Role, Value Accessibility Checker
Covers: 4.1.2 Name, Role, Value
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


def check_name_role_value(soup, url, html=None):
    """Check that all UI components have accessible name, role, and value."""
    issues = []
    passed = []
    warnings = []
    
    # Check buttons
    buttons = soup.find_all('button')
    for btn in buttons:
        text = btn.get_text(strip=True)
        aria_label = btn.get('aria-label')
        aria_labelledby = btn.get('aria-labelledby')
        title = btn.get('title')
        img = btn.find('img')
        svg = btn.find('svg')
        
        has_name = text or aria_label or title
        
        # Check images inside button
        if img and not text:
            img_alt = img.get('alt', '')
            has_name = has_name or img_alt
        
        # Check SVG inside button
        if svg and not text:
            svg_title = svg.find('title')
            svg_label = svg.get('aria-label')
            has_name = has_name or svg_title or svg_label
        
        # Check aria-labelledby reference
        if aria_labelledby and not has_name:
            ref = soup.find(id=aria_labelledby)
            if ref and ref.get_text(strip=True):
                has_name = True
        
        if not has_name:
            issues.append(Issue(
                rule_id="4.1.2",
                criterion_id="4.1.2",
                criterion_name="Navn, rolle, verdi",
                criterion_name_en="Name, Role, Value",
                level="A",
                impact="critical",
                element=str(btn)[:200],
                selector="button",
                issue="Button has no accessible name",
                fix="Add text content, aria-label, or image with alt text"
            ))
        else:
            passed.append(f"4.1.2: Button has accessible name")
    
    # Check inputs (non-hidden)
    inputs = soup.find_all('input')
    for inp in inputs:
        inp_type = inp.get('type', 'text')
        
        # Skip hidden and submit/image types
        if inp_type in ['hidden', 'submit', 'reset', 'button', 'image']:
            continue
        
        inp_id = inp.get('id', '')
        aria_label = inp.get('aria-label')
        aria_labelledby = inp.get('aria-labelledby')
        title = inp.get('title')
        placeholder = inp.get('placeholder')
        
        has_label = False
        
        # Check for associated label
        if inp_id:
            label = soup.find('label', {'for': inp_id})
            if label and label.get_text(strip=True):
                has_label = True
        
        # Check if wrapped in label
        parent = inp.parent
        while parent:
            if parent.name == 'label':
                if parent.get_text(strip=True):
                    has_label = True
                break
            parent = parent.parent
        
        # Check ARIA
        if aria_label or title:
            has_label = True
        
        if aria_labelledby:
            ref = soup.find(id=aria_labelledby)
            if ref and ref.get_text(strip=True):
                has_label = True
        
        if not has_label:
            issues.append(Issue(
                rule_id="4.1.2",
                criterion_id="4.1.2",
                criterion_name="Navn, rolle, verdi",
                criterion_name_en="Name, Role, Value",
                level="A",
                impact="critical",
                element=str(inp)[:200],
                selector=f'input[type="{inp_type}"]',
                issue=f"Input ({inp_type}) has no accessible name",
                fix="Add associated label, aria-label, or aria-labelledby"
            ))
        else:
            passed.append(f"4.1.2: Input has accessible name")
    
    # Check select elements
    selects = soup.find_all('select')
    for select in selects:
        select_id = select.get('id', '')
        aria_label = select.get('aria-label')
        
        has_label = bool(aria_label)
        
        if select_id:
            label = soup.find('label', {'for': select_id})
            if label:
                has_label = True
        
        if not has_label:
            issues.append(Issue(
                rule_id="4.1.2",
                criterion_id="4.1.2",
                criterion_name="Navn, rolle, verdi",
                criterion_name_en="Name, Role, Value",
                level="A",
                impact="critical",
                element=str(select)[:200],
                selector="select",
                issue="Select element has no accessible name",
                fix="Add associated label or aria-label"
            ))
    
    # Check textareas
    textareas = soup.find_all('textarea')
    for ta in textareas:
        ta_id = ta.get('id', '')
        aria_label = ta.get('aria-label')
        
        has_label = bool(aria_label)
        
        if ta_id:
            label = soup.find('label', {'for': ta_id})
            if label:
                has_label = True
        
        if not has_label:
            issues.append(Issue(
                rule_id="4.1.2",
                criterion_id="4.1.2",
                criterion_name="Navn, rolle, verdi",
                criterion_name_en="Name, Role, Value",
                level="A",
                impact="critical",
                element=str(ta)[:200],
                selector="textarea",
                issue="Textarea has no accessible name",
                fix="Add associated label or aria-label"
            ))
    
    # Check custom components with role
    custom_widgets = soup.find_all(role=['checkbox', 'radio', 'switch', 'slider', 'spinbutton'])
    for widget in custom_widgets:
        role = widget.get('role')
        text = widget.get_text(strip=True)
        aria_label = widget.get('aria-label')
        aria_labelledby = widget.get('aria-labelledby')
        
        has_name = text or aria_label
        
        if aria_labelledby:
            ref = soup.find(id=aria_labelledby)
            if ref:
                has_name = True
        
        if not has_name:
            issues.append(Issue(
                rule_id="4.1.2",
                criterion_id="4.1.2",
                criterion_name="Navn, rolle, verdi",
                criterion_name_en="Name, Role, Value",
                level="A",
                impact="critical",
                element=str(widget)[:200],
                selector=f'[role="{role}"]',
                issue=f"Custom {role} widget has no accessible name",
                fix="Add aria-label or aria-labelledby"
            ))
        
        # Check for required state attributes
        state_attrs = {
            'checkbox': 'aria-checked',
            'radio': 'aria-checked',
            'switch': 'aria-checked',
            'slider': 'aria-valuenow',
            'spinbutton': 'aria-valuenow',
        }
        
        required_attr = state_attrs.get(role)
        if required_attr and not widget.get(required_attr):
            issues.append(Issue(
                rule_id="4.1.2",
                criterion_id="4.1.2",
                criterion_name="Navn, rolle, verdi",
                criterion_name_en="Name, Role, Value",
                level="A",
                impact="serious",
                element=str(widget)[:200],
                selector=f'[role="{role}"]',
                issue=f"Custom {role} missing required {required_attr} attribute",
                fix=f"Add {required_attr} to communicate widget state"
            ))
    
    # Check expandable elements
    expandables = soup.find_all(attrs={'aria-expanded': True})
    for elem in expandables:
        controls = elem.get('aria-controls')
        if not controls:
            warnings.append("4.1.2: Element with aria-expanded should have aria-controls")
    
    return issues, passed, warnings
