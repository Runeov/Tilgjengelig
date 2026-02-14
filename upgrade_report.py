import sys
import os
from bs4 import BeautifulSoup
from checker import SiteResult, PageResult, Issue, AccessibilityStatementResult
from enhanced_html_report import generate_enhanced_html_report

def parse_report(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract Site Info
    header = soup.find('div', class_='header')
    base_url = "Unknown"
    timestamp = "Unknown"
    if header:
        for p in header.find_all('p'):
            text = p.get_text()
            if "Nettsted:" in text:
                base_url = text.replace("Nettsted:", "").strip()
            if "Dato:" in text:
                timestamp = text.replace("Dato:", "").strip()
    
    site_result = SiteResult(base_url=base_url, timestamp=timestamp)
    
    # Extract Accessibility Statement Info
    stmt_section = soup.find('div', class_='statement-section')
    if stmt_section:
        stmt_result = AccessibilityStatementResult()
        
        # Check status items
        items = stmt_section.find_all('div', class_='statement-item')
        for item in items:
            text = item.get_text(strip=True)
            if "Tilgjengelighetserklæring funnet" in text:
                stmt_result.has_statement_page = True
            if "Mangler" in text:
                stmt_result.has_statement_page = False
            
            link = item.find('a')
            if link:
                href = link.get('href')
                if "uustatus.no" in href:
                    stmt_result.uustatus_url = href
                else:
                    stmt_result.statement_page_url = href
        
        site_result.accessibility_statement = stmt_result

    # Extract Pages
    pages = soup.find_all('div', class_='page')
    for page_div in pages:
        header_div = page_div.find('div', class_='page-header')
        title = header_div.find('h3').get_text(strip=True) if header_div.find('h3') else "Unknown Title"
        url_div = header_div.find('div', class_='page-url')
        url = url_div.get_text(strip=True) if url_div else "Unknown URL"
        
        page_result = PageResult(url=url, title=title, timestamp=timestamp)
        
        # Extract Issues
        issues_div = page_div.find('div', class_='issues')
        if issues_div:
            # Issues are inside details/summary or directly in issues div?
            # Old format: <details><summary>...</summary><div class="issue">...</div></details>
            
            # We need to find all .issue divs, whether inside details or not
            issue_divs = issues_div.find_all('div', class_='issue')
            
            for issue_div in issue_divs:
                # Extract issue details
                header = issue_div.find('div', class_='issue-header')
                
                # Rule ID and Criterion
                rule_span = header.find('span', class_='rule-id')
                rule_id = rule_span.get_text(strip=True).replace("Testregel", "").strip() if rule_span else "Unknown"
                
                crit_span = header.find('span', class_='criterion')
                crit_text = crit_span.get_text(strip=True) if crit_span else ""
                # Format: (1.1.1 - Nivå A)
                criterion_id = "Unknown"
                level = "Unknown"
                if "(" in crit_text and ")" in crit_text:
                    inner = crit_text.strip("()")
                    parts = inner.split("-")
                    if len(parts) >= 2:
                        criterion_id = parts[0].strip()
                        level = parts[1].replace("Nivå", "").strip()
                
                # Impact
                impact_span = header.find('span', class_='impact')
                impact = "moderate"
                if impact_span:
                    classes = impact_span.get('class', [])
                    for c in classes:
                        if c in ['critical', 'serious', 'moderate', 'minor']:
                            impact = c
                            break
                
                # Issue Text
                p_text = issue_div.find('p')
                issue_text = p_text.get_text(strip=True) if p_text else ""
                
                # Element
                el_div = issue_div.find('div', class_='element')
                element = el_div.get_text(strip=True) if el_div else ""
                
                # Fix
                fix_div = issue_div.find('div', class_='fix')
                fix = fix_div.get_text(strip=True).replace("💡 Løsning:", "").strip() if fix_div else ""
                
                # Criterion Name - Try to get from summary if inside details
                criterion_name = "Unknown"
                parent_details = issue_div.find_parent('details')
                if parent_details:
                    summary = parent_details.find('summary')
                    if summary:
                        sum_text = summary.get_text(strip=True)
                        # Format: 1.1.1 Non-text Content (5 avvik)
                        # We want "Non-text Content"
                        # Remove count at end
                        if "(" in sum_text:
                            sum_text = sum_text.rsplit("(", 1)[0].strip()
                        # Remove ID at start
                        if sum_text.startswith(criterion_id):
                            sum_text = sum_text[len(criterion_id):].strip()
                        criterion_name = sum_text

                issue_obj = Issue(
                    rule_id=rule_id,
                    criterion_id=criterion_id,
                    criterion_name=criterion_name,
                    criterion_name_en=criterion_name, # Assuming same
                    level=level,
                    impact=impact,
                    element=element,
                    selector="", # Not preserved in HTML
                    issue=issue_text,
                    fix=fix
                )
                page_result.issues.append(issue_obj)
        
        site_result.pages.append(page_result)
        
    return site_result

def main():
    if len(sys.argv) < 2:
        print("Usage: python upgrade_report.py <html_file>")
        sys.exit(1)
        
    filepath = sys.argv[1]
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        sys.exit(1)
        
    print(f"Reading {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    print("Parsing report...")
    try:
        result = parse_report(content)
        print(f"Found {len(result.pages)} pages and {result.summary['issues']} issues.")
        
        print("Generating enhanced report...")
        new_html = generate_enhanced_html_report(result)
        
        print(f"Writing back to {filepath}...")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_html)
            
        print("Done!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
