"""
WCAG Forms Accessibility Checker
Covers: 1.3.1, 2.4.6, 3.3.1, 3.3.2, 4.1.2
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


def check_forms(soup, url, html=None):
    """Check forms for accessibility issues."""
    issues = []
    passed = []
    warnings = []
    
    # Check all form inputs
    inputs = soup.find_all(['input', 'select', 'textarea'])
    
    for inp in inputs:
        inp_type = inp.get('type', 'text')
        inp_id = inp.get('id', '')
        inp_name = inp.get('name', '')
        element_str = str(inp)[:200]
        
        # Skip hidden and submit/button inputs
        if inp_type in ['hidden', 'submit', 'button', 'reset', 'image']:
            continue
        
        # Check for label
        has_label = False
        label_method = None
        
        # Method 1: Associated label via for/id
        if inp_id:
            label = soup.find('label', {'for': inp_id})
            if label and label.get_text(strip=True):
                has_label = True
                label_method = 'for/id'
        
        # Method 2: Wrapped in label
        if not has_label:
            parent = inp.parent
            while parent:
                if parent.name == 'label':
                    label_text = parent.get_text(strip=True)
                    # Remove the input value from label text
                    if label_text:
                        has_label = True
                        label_method = 'wrapper'
                    break
                parent = parent.parent
        
        # Method 3: aria-label
        if not has_label and inp.get('aria-label'):
            has_label = True
            label_method = 'aria-label'
        
        # Method 4: aria-labelledby
        if not has_label and inp.get('aria-labelledby'):
            labelledby_id = inp.get('aria-labelledby')
            ref_element = soup.find(id=labelledby_id)
            if ref_element and ref_element.get_text(strip=True):
                has_label = True
                label_method = 'aria-labelledby'
        
        # Method 5: title attribute (less preferred)
        if not has_label and inp.get('title'):
            has_label = True
            label_method = 'title'
            warnings.append(f"3.3.2: Input uses title for label (less accessible): {inp_name or inp_id}")
        
        # Method 6: placeholder (not acceptable as only label)
        placeholder = inp.get('placeholder')
        
        if not has_label:
            if placeholder:
                issues.append(Issue(
                    rule_id="3.3.2",
                    criterion_id="3.3.2",
                    criterion_name="Ledetekster eller instruksjoner",
                    criterion_name_en="Labels or Instructions",
                    level="A",
                    impact="critical",
                    element=element_str,
                    selector=f'input[name="{inp_name}"]' if inp_name else 'input',
                    issue="Form input only has placeholder, no proper label",
                    fix="Add a <label> element with for attribute, or aria-label. Placeholder disappears when typing."
                ))
            else:
                issues.append(Issue(
                    rule_id="3.3.2",
                    criterion_id="3.3.2",
                    criterion_name="Ledetekster eller instruksjoner",
                    criterion_name_en="Labels or Instructions",
                    level="A",
                    impact="critical",
                    element=element_str,
                    selector=f'input[name="{inp_name}"]' if inp_name else 'input',
                    issue="Form input has no label",
                    fix="Add a <label> element with for attribute pointing to input id"
                ))
        else:
            passed.append(f"3.3.2: Input has label via {label_method}: {inp_name or inp_id}")
        
        # Check required fields
        if inp.get('required') or inp.get('aria-required') == 'true':
            # Should have visible indication
            passed.append(f"3.3.2: Required field marked: {inp_name or inp_id}")
        
        # Check autocomplete for personal data fields
        personal_fields = {
            'name': 'name', 'email': 'email', 'tel': 'tel', 'phone': 'tel',
            'address': 'street-address', 'zip': 'postal-code', 'postnr': 'postal-code',
            'city': 'address-level2', 'country': 'country-name',
            'firstname': 'given-name', 'fornavn': 'given-name',
            'lastname': 'family-name', 'etternavn': 'family-name',
            'cc-number': 'cc-number', 'cc-name': 'cc-name'
        }
        
        field_name = (inp_name or inp_id or '').lower()
        for key, autocomplete_value in personal_fields.items():
            if key in field_name:
                if not inp.get('autocomplete'):
                    issues.append(Issue(
                        rule_id="1.3.5",
                        criterion_id="1.3.5",
                        criterion_name="Identifiser inndataformål",
                        criterion_name_en="Identify Input Purpose",
                        level="AA",
                        impact="moderate",
                        element=element_str,
                        selector=f'input[name="{inp_name}"]' if inp_name else 'input',
                        issue=f"Personal data field '{field_name}' missing autocomplete attribute",
                        fix=f"Add autocomplete='{autocomplete_value}' to help users fill in the form"
                    ))
                break
    
    # Check for fieldset/legend on radio/checkbox groups
    radio_groups = {}
    for inp in soup.find_all('input', {'type': ['radio', 'checkbox']}):
        name = inp.get('name', '')
        if name:
            if name not in radio_groups:
                radio_groups[name] = []
            radio_groups[name].append(inp)
    
    for name, inputs in radio_groups.items():
        if len(inputs) > 1:
            # Check if wrapped in fieldset
            first_input = inputs[0]
            parent = first_input.parent
            has_fieldset = False
            while parent:
                if parent.name == 'fieldset':
                    legend = parent.find('legend')
                    if legend and legend.get_text(strip=True):
                        has_fieldset = True
                        passed.append(f"1.3.1: Radio/checkbox group '{name}' has fieldset with legend")
                    break
                parent = parent.parent
            
            if not has_fieldset:
                issues.append(Issue(
                    rule_id="1.3.1",
                    criterion_id="1.3.1",
                    criterion_name="Informasjon og relasjoner",
                    criterion_name_en="Info and Relationships",
                    level="A",
                    impact="moderate",
                    element=str(inputs[0])[:200],
                    selector=f'input[name="{name}"]',
                    issue=f"Radio/checkbox group '{name}' not wrapped in fieldset with legend",
                    fix="Wrap related radio buttons or checkboxes in <fieldset> with <legend>"
                ))
    
    # Check forms for error identification
    for form in soup.find_all('form'):
        # Check if form has validation attributes
        has_validation = form.find_all(['input', 'select', 'textarea'], 
                                       attrs={'required': True}) or \
                        form.find_all(['input', 'select', 'textarea'],
                                      attrs={'pattern': True})
        
        if has_validation:
            # Should have aria-describedby or visible error messages
            warnings.append("3.3.1: Form has validation - ensure errors are clearly identified")
    
    return issues, passed, warnings
