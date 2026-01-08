"""
WCAG 1.3.1 Structure Checker
Checks page structure including landmarks and regions.
"""

from bs4 import BeautifulSoup

RULE_INFO = {
    "1.3.1d": {
        "criterion": "1.3.1",
        "criterion_name": "Informasjon og relasjoner",
        "criterion_name_en": "Info and Relationships",
        "level": "A",
    },
    "4.1.1a": {
        "criterion": "4.1.1",
        "criterion_name": "Parsing",
        "criterion_name_en": "Parsing",
        "level": "A",
    }
}


def check_structure(soup, url, **kwargs):
    """
    Check page structure for proper landmarks and valid markup.
    
    Returns tuple of (issues, passed, warnings).
    """
    issues = []
    passed = []
    warnings = []
    
    rule = RULE_INFO["1.3.1d"]
    
    # Check for main landmark
    main = soup.find('main') or soup.find(attrs={'role': 'main'})
    if not main:
        warnings.append({
            "rule_id": "1.3.1d",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "moderate",
            "element": "Page",
            "selector": "",
            "issue": "Siden mangler <main> element eller role='main'",
            "fix": "Legg til <main> element rundt hovedinnholdet"
        })
    else:
        passed.append({
            "rule_id": "1.3.1d",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "message": "Siden har <main> landmark"
        })
    
    # Check for navigation
    nav = soup.find('nav') or soup.find(attrs={'role': 'navigation'})
    if not nav:
        warnings.append({
            "rule_id": "1.3.1d",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "minor",
            "element": "Page",
            "selector": "",
            "issue": "Siden mangler <nav> element for navigasjon",
            "fix": "Bruk <nav> element rundt navigasjonsmenyer"
        })
    
    # Check for header
    header = soup.find('header') or soup.find(attrs={'role': 'banner'})
    if not header:
        warnings.append({
            "rule_id": "1.3.1d",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "minor",
            "element": "Page",
            "selector": "",
            "issue": "Siden mangler <header> element",
            "fix": "Bruk <header> element for sidens toppseksjon"
        })
    
    # Check for duplicate IDs (4.1.1)
    rule_parsing = RULE_INFO["4.1.1a"]
    all_ids = {}
    duplicate_ids = []
    
    for element in soup.find_all(id=True):
        element_id = element.get('id')
        if element_id in all_ids:
            duplicate_ids.append((element_id, element))
        else:
            all_ids[element_id] = element
    
    for dup_id, element in duplicate_ids[:5]:
        element_str = str(element)[:200]
        issues.append({
            "rule_id": "4.1.1a",
            "criterion_id": rule_parsing["criterion"],
            "criterion_name": rule_parsing["criterion_name"],
            "criterion_name_en": rule_parsing["criterion_name_en"],
            "level": rule_parsing["level"],
            "impact": "serious",
            "element": element_str,
            "selector": f"#{dup_id}",
            "issue": f"Duplisert ID: '{dup_id}'",
            "fix": "ID-er må være unike. Gi elementet en unik ID."
        })
    
    if len(duplicate_ids) > 5:
        warnings.append({
            "rule_id": "4.1.1a",
            "criterion_id": rule_parsing["criterion"],
            "criterion_name": rule_parsing["criterion_name"],
            "criterion_name_en": rule_parsing["criterion_name_en"],
            "level": rule_parsing["level"],
            "impact": "moderate",
            "element": "Multiple elements",
            "selector": "",
            "issue": f"Fant {len(duplicate_ids)} dupliserte ID-er (viser kun de første 5)",
            "fix": "Gjennomgå alle ID-er og sørg for at de er unike"
        })
    
    if len(duplicate_ids) == 0:
        passed.append({
            "rule_id": "4.1.1a",
            "criterion_id": rule_parsing["criterion"],
            "criterion_name": rule_parsing["criterion_name"],
            "message": f"Alle {len(all_ids)} ID-er er unike"
        })
    
    # Check for empty containers (divs/spans with no content)
    empty_containers = []
    for element in soup.find_all(['div', 'span', 'p']):
        text = element.get_text(strip=True)
        children = list(element.children)
        # Element is empty if no text and no meaningful children
        if not text and not any(hasattr(c, 'name') and c.name not in [None, 'br'] for c in children):
            # Check if it has aria attributes (might be for ARIA)
            if not any(attr.startswith('aria-') for attr in element.attrs.keys()):
                empty_containers.append(element)
    
    # Only report if there are many empty containers (might indicate issue)
    if len(empty_containers) > 10:
        warnings.append({
            "rule_id": "1.3.1d",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "minor",
            "element": "Multiple elements",
            "selector": "",
            "issue": f"Fant {len(empty_containers)} tomme container-elementer",
            "fix": "Fjern unødvendige tomme elementer eller legg til innhold"
        })
    
    return issues, passed, warnings
