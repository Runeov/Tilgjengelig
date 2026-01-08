"""
WCAG 4.1.2 Name, Role, Value Checker
Ensures interactive elements have accessible names and proper roles.

Checks:
- Buttons have accessible names
- Links have accessible names  
- Form inputs have associated labels
- Image buttons have alt text
- Custom widgets have proper ARIA
"""

import re
from bs4 import BeautifulSoup

# UU Test Rule mapping
RULE_INFO = {
    "4.1.2a": {
        "criterion": "4.1.2",
        "criterion_name": "Navn, rolle, verdi",
        "criterion_name_en": "Name, Role, Value",
        "level": "A",
        "description": "Skjemaelementer",
    },
    "4.1.2b": {
        "criterion": "4.1.2",
        "criterion_name": "Navn, rolle, verdi", 
        "criterion_name_en": "Name, Role, Value",
        "level": "A",
        "description": "Knapper",
    },
    "4.1.2c": {
        "criterion": "4.1.2",
        "criterion_name": "Navn, rolle, verdi",
        "criterion_name_en": "Name, Role, Value", 
        "level": "A",
        "description": "Iframe",
    },
    "4.1.2d": {
        "criterion": "4.1.2",
        "criterion_name": "Navn, rolle, verdi",
        "criterion_name_en": "Name, Role, Value",
        "level": "A",
        "description": "Menyelementer",
    },
}


def get_accessible_name(element, soup):
    """
    Calculate the accessible name for an element.
    Following the accessible name computation algorithm (simplified).
    """
    # 1. aria-labelledby (highest priority)
    labelledby = element.get('aria-labelledby')
    if labelledby:
        names = []
        for id_ref in labelledby.split():
            referenced = soup.find(id=id_ref)
            if referenced:
                names.append(referenced.get_text(strip=True))
        if names:
            return ' '.join(names)
    
    # 2. aria-label
    aria_label = element.get('aria-label', '').strip()
    if aria_label:
        return aria_label
    
    # 3. For inputs, check for associated label
    if element.name in ('input', 'select', 'textarea'):
        # Check for label with for attribute
        element_id = element.get('id')
        if element_id:
            label = soup.find('label', attrs={'for': element_id})
            if label:
                return label.get_text(strip=True)
        
        # Check for wrapping label
        parent_label = element.find_parent('label')
        if parent_label:
            # Get label text excluding the input itself
            label_text = parent_label.get_text(strip=True)
            return label_text
        
        # For input type="image", use alt
        if element.get('type') == 'image':
            alt = element.get('alt', '').strip()
            if alt:
                return alt
        
        # Placeholder is not a valid accessible name but some screen readers use it
        placeholder = element.get('placeholder', '').strip()
        if placeholder:
            return f"(placeholder: {placeholder})"
    
    # 4. For buttons, get text content
    if element.name == 'button':
        text = element.get_text(strip=True)
        if text:
            return text
        # Check for aria-label on child elements
        for child in element.descendants:
            if hasattr(child, 'get') and child.get('aria-label'):
                return child.get('aria-label')
    
    # 5. For links, get text content
    if element.name == 'a':
        text = element.get_text(strip=True)
        if text:
            return text
        # Check for image with alt inside link
        img = element.find('img')
        if img and img.get('alt'):
            return img.get('alt')
    
    # 6. Title attribute (last resort)
    title = element.get('title', '').strip()
    if title:
        return f"(title: {title})"
    
    # 7. For images, use alt
    if element.name == 'img':
        alt = element.get('alt', '').strip()
        if alt:
            return alt
    
    return None


def check_buttons(soup, issues, passed, warnings):
    """Check all buttons for accessible names."""
    rule = RULE_INFO["4.1.2b"]
    
    # Find all button-like elements
    buttons = soup.find_all('button')
    input_buttons = soup.find_all('input', type=re.compile(r'^(submit|button|reset|image)$', re.I))
    role_buttons = soup.find_all(attrs={'role': 'button'})
    
    all_buttons = list(buttons) + list(input_buttons) + list(role_buttons)
    problem_count = 0
    
    for button in all_buttons:
        name = get_accessible_name(button, soup)
        
        # Check if name is missing or only whitespace
        if not name or (name.startswith('(') and name.endswith(')')):
            problem_count += 1
            if problem_count <= 5:  # Limit reported issues
                element_str = str(button)[:200]
                
                # Determine button type for better message
                if button.name == 'input' and button.get('type') == 'image':
                    issue_msg = "Bildeknapp mangler tekstalternativ (alt-attributt)"
                    fix_msg = "Legg til alt-attributt som beskriver knappens funksjon"
                else:
                    issue_msg = "Knapp mangler tilgjengelig navn"
                    fix_msg = "Legg til tekst i knappen, eller bruk aria-label"
                
                issues.append({
                    "rule_id": "4.1.2b",
                    "criterion_id": rule["criterion"],
                    "criterion_name": rule["criterion_name"],
                    "criterion_name_en": rule["criterion_name_en"],
                    "level": rule["level"],
                    "impact": "critical",
                    "element": element_str,
                    "selector": _get_selector(button),
                    "issue": issue_msg,
                    "fix": fix_msg
                })
    
    if problem_count > 5:
        warnings.append({
            "rule_id": "4.1.2b",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "serious",
            "element": "Multiple buttons",
            "selector": "",
            "issue": f"Fant {problem_count} knapper uten tilgjengelig navn (viser kun de første 5)",
            "fix": "Gjennomgå alle knapper og sørg for at de har tekstinnhold eller aria-label"
        })
    
    if len(all_buttons) > 0 and problem_count == 0:
        passed.append({
            "rule_id": "4.1.2b",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "message": f"Alle {len(all_buttons)} knapper har tilgjengelige navn"
        })
    
    return problem_count


def check_links(soup, issues, passed, warnings):
    """Check all links for accessible names."""
    rule = RULE_INFO["4.1.2d"]  # Using menu elements rule for links
    
    links = soup.find_all('a', href=True)
    problem_count = 0
    
    for link in links:
        # Skip anchor links to same page
        href = link.get('href', '')
        if href.startswith('#') and len(href) <= 1:
            continue
        
        name = get_accessible_name(link, soup)
        
        if not name or name.strip() == '':
            problem_count += 1
            if problem_count <= 5:
                element_str = str(link)[:200]
                
                # Check if link contains only an image
                img = link.find('img')
                if img and not link.get_text(strip=True):
                    issue_msg = "Lenke inneholder kun bilde uten tekstalternativ"
                    fix_msg = "Legg til alt-tekst på bildet, eller aria-label på lenken"
                else:
                    issue_msg = "Lenke mangler tilgjengelig navn"
                    fix_msg = "Legg til lenketekst eller aria-label"
                
                issues.append({
                    "rule_id": "4.1.2d",
                    "criterion_id": rule["criterion"],
                    "criterion_name": rule["criterion_name"],
                    "criterion_name_en": rule["criterion_name_en"],
                    "level": rule["level"],
                    "impact": "critical",
                    "element": element_str,
                    "selector": _get_selector(link),
                    "issue": issue_msg,
                    "fix": fix_msg
                })
    
    if problem_count > 5:
        warnings.append({
            "rule_id": "4.1.2d",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "serious",
            "element": "Multiple links",
            "selector": "",
            "issue": f"Fant {problem_count} lenker uten tilgjengelig navn (viser kun de første 5)",
            "fix": "Gjennomgå alle lenker og sørg for at de har tekst eller aria-label"
        })
    
    if len(links) > 0 and problem_count == 0:
        passed.append({
            "rule_id": "4.1.2d",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "message": f"Alle {len(links)} lenker har tilgjengelige navn"
        })
    
    return problem_count


def check_form_elements(soup, issues, passed, warnings):
    """Check all form elements for accessible names."""
    rule = RULE_INFO["4.1.2a"]
    
    # Form elements that need labels
    inputs = soup.find_all('input', type=lambda x: x not in ['hidden', 'submit', 'button', 'reset', 'image'])
    selects = soup.find_all('select')
    textareas = soup.find_all('textarea')
    
    all_inputs = list(inputs) + list(selects) + list(textareas)
    problem_count = 0
    
    for element in all_inputs:
        name = get_accessible_name(element, soup)
        
        # Placeholder alone is not sufficient
        is_placeholder_only = name and name.startswith('(placeholder:')
        
        if not name or is_placeholder_only:
            problem_count += 1
            if problem_count <= 5:
                element_str = str(element)[:200]
                
                input_type = element.get('type', element.name)
                if is_placeholder_only:
                    issue_msg = f"Skjemafelt ({input_type}) bruker kun placeholder som etikett"
                    fix_msg = "Legg til <label> element eller aria-label. Placeholder er ikke tilstrekkelig."
                else:
                    issue_msg = f"Skjemafelt ({input_type}) mangler etikett"
                    fix_msg = "Legg til <label> element med for-attributt, eller bruk aria-label"
                
                issues.append({
                    "rule_id": "4.1.2a",
                    "criterion_id": rule["criterion"],
                    "criterion_name": rule["criterion_name"],
                    "criterion_name_en": rule["criterion_name_en"],
                    "level": rule["level"],
                    "impact": "critical",
                    "element": element_str,
                    "selector": _get_selector(element),
                    "issue": issue_msg,
                    "fix": fix_msg
                })
    
    if problem_count > 5:
        warnings.append({
            "rule_id": "4.1.2a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "serious",
            "element": "Multiple form elements",
            "selector": "",
            "issue": f"Fant {problem_count} skjemafelt uten etikett (viser kun de første 5)",
            "fix": "Gjennomgå alle skjemafelt og sørg for at de har tilhørende <label>"
        })
    
    if len(all_inputs) > 0 and problem_count == 0:
        passed.append({
            "rule_id": "4.1.2a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "message": f"Alle {len(all_inputs)} skjemafelt har etiketter"
        })
    
    return problem_count


def check_iframes(soup, issues, passed, warnings):
    """Check all iframes for accessible names."""
    rule = RULE_INFO["4.1.2c"]
    
    iframes = soup.find_all('iframe')
    problem_count = 0
    
    for iframe in iframes:
        # Check for title or aria-label
        title = iframe.get('title', '').strip()
        aria_label = iframe.get('aria-label', '').strip()
        
        if not title and not aria_label:
            problem_count += 1
            if problem_count <= 5:
                element_str = str(iframe)[:200]
                src = iframe.get('src', 'ukjent kilde')
                
                issues.append({
                    "rule_id": "4.1.2c",
                    "criterion_id": rule["criterion"],
                    "criterion_name": rule["criterion_name"],
                    "criterion_name_en": rule["criterion_name_en"],
                    "level": rule["level"],
                    "impact": "serious",
                    "element": element_str,
                    "selector": _get_selector(iframe),
                    "issue": f"Iframe ({src[:50]}) mangler tilgjengelig navn",
                    "fix": "Legg til title-attributt som beskriver iframens innhold"
                })
    
    if len(iframes) > 0 and problem_count == 0:
        passed.append({
            "rule_id": "4.1.2c",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "message": f"Alle {len(iframes)} iframes har tilgjengelige navn"
        })
    
    return problem_count


def check_name_role_value(soup, url, **kwargs):
    """
    Check that all interactive elements have accessible names, roles, and values.
    
    Returns tuple of (issues, passed, warnings).
    """
    issues = []
    passed = []
    warnings = []
    
    # Check different element types
    button_issues = check_buttons(soup, issues, passed, warnings)
    link_issues = check_links(soup, issues, passed, warnings)
    form_issues = check_form_elements(soup, issues, passed, warnings)
    iframe_issues = check_iframes(soup, issues, passed, warnings)
    
    total_issues = button_issues + link_issues + form_issues + iframe_issues
    
    if total_issues == 0 and len(issues) == 0:
        passed.append({
            "rule_id": "4.1.2",
            "criterion_id": "4.1.2",
            "criterion_name": "Navn, rolle, verdi",
            "message": "Alle interaktive elementer har tilgjengelige navn"
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
