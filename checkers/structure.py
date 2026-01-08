"""
WCAG Structure Accessibility Checker
Covers: 1.3.1 Info and Relationships, 2.4.1 Bypass Blocks, 4.1.1 Parsing
"""

from dataclasses import dataclass
import re
from collections import Counter


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


def check_structure(soup, url, html=None):
    """Check page structure for accessibility issues."""
    issues = []
    passed = []
    warnings = []
    
    # Check for landmark regions
    landmarks = {
        'header': soup.find_all('header') + soup.find_all(role='banner'),
        'nav': soup.find_all('nav') + soup.find_all(role='navigation'),
        'main': soup.find_all('main') + soup.find_all(role='main'),
        'footer': soup.find_all('footer') + soup.find_all(role='contentinfo'),
        'aside': soup.find_all('aside') + soup.find_all(role='complementary'),
    }
    
    # Check for main landmark
    if not landmarks['main']:
        issues.append(Issue(
            rule_id="1.3.1",
            criterion_id="1.3.1",
            criterion_name="Informasjon og relasjoner",
            criterion_name_en="Info and Relationships",
            level="A",
            impact="moderate",
            element="<body>",
            selector="body",
            issue="Page has no main landmark",
            fix="Add <main> element or role='main' to wrap primary content"
        ))
    elif len(landmarks['main']) > 1:
        issues.append(Issue(
            rule_id="1.3.1",
            criterion_id="1.3.1",
            criterion_name="Informasjon og relasjoner",
            criterion_name_en="Info and Relationships",
            level="A",
            impact="moderate",
            element="<main>",
            selector="main",
            issue=f"Page has {len(landmarks['main'])} main landmarks (should have 1)",
            fix="Use only one <main> element per page"
        ))
    else:
        passed.append("1.3.1: Page has exactly one main landmark")
    
    # Check navigation landmark
    if not landmarks['nav']:
        warnings.append("2.4.1: Page has no navigation landmark - consider adding <nav>")
    else:
        # Multiple navs should have labels
        if len(landmarks['nav']) > 1:
            for nav in landmarks['nav']:
                label = nav.get('aria-label') or nav.get('aria-labelledby')
                if not label:
                    issues.append(Issue(
                        rule_id="1.3.1",
                        criterion_id="1.3.1",
                        criterion_name="Informasjon og relasjoner",
                        criterion_name_en="Info and Relationships",
                        level="A",
                        impact="moderate",
                        element=str(nav)[:200],
                        selector="nav",
                        issue="Multiple nav elements exist but this one has no label",
                        fix="Add aria-label to distinguish between navigation regions (e.g., 'Main navigation', 'Footer navigation')"
                    ))
        passed.append(f"2.4.1: Page has {len(landmarks['nav'])} navigation landmark(s)")
    
    # Check for skip link
    first_link = soup.find('a')
    has_skip_link = False
    
    if first_link:
        href = first_link.get('href', '')
        text = first_link.get_text(strip=True).lower()
        
        if href.startswith('#') and ('skip' in text or 'hopp' in text or 'main' in text or 'innhold' in text):
            has_skip_link = True
            passed.append("2.4.1: Page has skip link")
    
    if not has_skip_link:
        # Check first few links
        for link in soup.find_all('a')[:5]:
            href = link.get('href', '')
            text = link.get_text(strip=True).lower()
            if href.startswith('#') and ('skip' in text or 'hopp' in text):
                has_skip_link = True
                break
        
        if not has_skip_link:
            issues.append(Issue(
                rule_id="2.4.1",
                criterion_id="2.4.1",
                criterion_name="Hopp over blokker",
                criterion_name_en="Bypass Blocks",
                level="A",
                impact="moderate",
                element="<body>",
                selector="body",
                issue="Page has no skip link to bypass navigation",
                fix="Add a skip link at the start of the page: <a href='#main'>Hopp til hovedinnhold</a>"
            ))
    
    # Check for duplicate IDs
    if html:
        id_pattern = re.compile(r'id=["\']([^"\']+)["\']', re.I)
        all_ids = id_pattern.findall(html)
        id_counts = Counter(all_ids)
        
        duplicates = {id_val: count for id_val, count in id_counts.items() if count > 1}
        
        for id_val, count in duplicates.items():
            issues.append(Issue(
                rule_id="4.1.1",
                criterion_id="4.1.1",
                criterion_name="Parsing",
                criterion_name_en="Parsing",
                level="A",
                impact="serious",
                element=f'id="{id_val}"',
                selector=f'[id="{id_val}"]',
                issue=f"Duplicate ID found: '{id_val}' appears {count} times",
                fix="Each ID must be unique on the page"
            ))
        
        if not duplicates:
            passed.append("4.1.1: No duplicate IDs found")
    
    # Check tables for proper structure
    tables = soup.find_all('table')
    for table in tables:
        element_str = str(table)[:200]
        
        # Check for caption or aria-label
        caption = table.find('caption')
        aria_label = table.get('aria-label')
        aria_labelledby = table.get('aria-labelledby')
        
        if not caption and not aria_label and not aria_labelledby:
            # Check if it's a data table (has th) vs layout table
            headers = table.find_all('th')
            if headers:
                issues.append(Issue(
                    rule_id="1.3.1",
                    criterion_id="1.3.1",
                    criterion_name="Informasjon og relasjoner",
                    criterion_name_en="Info and Relationships",
                    level="A",
                    impact="moderate",
                    element=element_str,
                    selector="table",
                    issue="Data table has no caption or label",
                    fix="Add <caption> element or aria-label to describe the table"
                ))
        
        # Check for th elements
        headers = table.find_all('th')
        if not headers:
            # Might be layout table
            if table.get('role') != 'presentation':
                warnings.append("1.3.1: Table has no header cells - add <th> if it's a data table, or role='presentation' if layout")
        else:
            # Check th has scope
            for th in headers:
                if not th.get('scope') and not th.get('id'):
                    issues.append(Issue(
                        rule_id="1.3.1",
                        criterion_id="1.3.1",
                        criterion_name="Informasjon og relasjoner",
                        criterion_name_en="Info and Relationships",
                        level="A",
                        impact="moderate",
                        element=str(th)[:200],
                        selector="th",
                        issue="Table header cell missing scope attribute",
                        fix="Add scope='col' or scope='row' to table headers"
                    ))
            
            passed.append(f"1.3.1: Table has {len(headers)} header cells")
    
    # Check lists are properly structured
    for ul in soup.find_all(['ul', 'ol']):
        children = [child for child in ul.children if child.name]
        non_li = [child for child in children if child.name != 'li']
        
        if non_li:
            issues.append(Issue(
                rule_id="1.3.1",
                criterion_id="1.3.1",
                criterion_name="Informasjon og relasjoner",
                criterion_name_en="Info and Relationships",
                level="A",
                impact="moderate",
                element=str(ul)[:200],
                selector=ul.name,
                issue=f"List contains non-li elements: {[c.name for c in non_li[:3]]}",
                fix="List elements (ul, ol) should only contain li children"
            ))
    
    # Check definition lists
    for dl in soup.find_all('dl'):
        children = [child for child in dl.children if child.name]
        valid_children = {'dt', 'dd', 'div'}
        invalid = [child for child in children if child.name not in valid_children]
        
        if invalid:
            issues.append(Issue(
                rule_id="1.3.1",
                criterion_id="1.3.1",
                criterion_name="Informasjon og relasjoner",
                criterion_name_en="Info and Relationships",
                level="A",
                impact="moderate",
                element=str(dl)[:200],
                selector="dl",
                issue=f"Definition list contains invalid elements: {[c.name for c in invalid[:3]]}",
                fix="Definition lists should only contain dt, dd, or div elements"
            ))
    
    return issues, passed, warnings
