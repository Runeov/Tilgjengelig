"""
WCAG Headings Accessibility Checker
Covers: 1.3.1 Info and Relationships, 2.4.6 Headings and Labels
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


def check_headings(soup, url, html=None):
    """Check heading structure for accessibility issues."""
    issues = []
    passed = []
    warnings = []
    
    headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    
    if not headings:
        issues.append(Issue(
            rule_id="1.3.1",
            criterion_id="1.3.1",
            criterion_name="Informasjon og relasjoner",
            criterion_name_en="Info and Relationships",
            level="A",
            impact="moderate",
            element="<body>",
            selector="body",
            issue="Page has no headings",
            fix="Add heading structure to organize page content"
        ))
        return issues, passed, warnings
    
    # Check for h1
    h1_count = len(soup.find_all('h1'))
    if h1_count == 0:
        issues.append(Issue(
            rule_id="2.4.2",
            criterion_id="2.4.2",
            criterion_name="Sidetittel",
            criterion_name_en="Page Titled",
            level="AA",
            impact="serious",
            element=str(soup.body)[:200] if soup.body else "<body>",
            selector="body",
            issue="Page is missing h1 heading",
            fix="Add a single h1 heading that describes the page content"
        ))
    elif h1_count > 1:
        warnings.append(f"2.4.2: Page has {h1_count} h1 headings (usually should have 1)")
    else:
        passed.append("2.4.2: Page has exactly one h1 heading")
    
    # Check heading hierarchy
    prev_level = 0
    first_heading = headings[0]
    first_level = int(first_heading.name[1])
    
    # First heading should ideally be h1
    if first_level != 1:
        issues.append(Issue(
            rule_id="1.3.1",
            criterion_id="1.3.1",
            criterion_name="Informasjon og relasjoner",
            criterion_name_en="Info and Relationships",
            level="A",
            impact="moderate",
            element=str(first_heading)[:200],
            selector=first_heading.name,
            issue=f"First heading is h{first_level}, should start with h1",
            fix="Start your heading structure with h1"
        ))
    
    for heading in headings:
        level = int(heading.name[1])
        text = heading.get_text(strip=True)
        element_str = str(heading)[:200]
        
        # Check for empty headings
        if not text:
            issues.append(Issue(
                rule_id="2.4.6",
                criterion_id="2.4.6",
                criterion_name="Overskrifter og ledetekster",
                criterion_name_en="Headings and Labels",
                level="AA",
                impact="serious",
                element=element_str,
                selector=heading.name,
                issue="Heading is empty",
                fix="Add descriptive text to the heading, or remove it if not needed"
            ))
            continue
        
        # Check for skipped levels (only going down)
        if prev_level > 0 and level > prev_level + 1:
            issues.append(Issue(
                rule_id="1.3.1",
                criterion_id="1.3.1",
                criterion_name="Informasjon og relasjoner",
                criterion_name_en="Info and Relationships",
                level="A",
                impact="moderate",
                element=element_str,
                selector=heading.name,
                issue=f"Heading level skipped: h{prev_level} to h{level}",
                fix=f"Don't skip heading levels. Use h{prev_level + 1} instead of h{level}"
            ))
        else:
            passed.append(f"1.3.1: Heading h{level} follows proper hierarchy")
        
        prev_level = level
    
    return issues, passed, warnings
