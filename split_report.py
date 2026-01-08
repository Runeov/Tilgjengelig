#!/usr/bin/env python3
"""
Split WCAG report into individual page reports.
"""
import re
import os
from pathlib import Path

def split_wcag_report(input_file, output_dir):
    """Split a WCAG HTML report into individual page reports."""
    
    # Create output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Read the original file
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract header (everything before first <div class="page">)
    header_match = re.search(r'(<div class="page">)', content)
    if not header_match:
        print("Could not find page sections in the file.")
        return
    
    header = content[:header_match.start()]
    
    # Split by page sections
    # Pattern to match each page div with all its content
    # We need to capture from <div class="page"> to the matching </div> that closes it
    # Using a more robust approach: find all page sections
    pages = []
    
    # Find all page divs using a simpler pattern first
    page_start_pattern = r'<div class="page">'
    page_end_pattern = r'</div>\s*</div>\s*'
    # Find positions of all page divs
    start_positions = [m.start() for m in re.finditer(page_start_pattern, content)]
    
    for i, start_pos in enumerate(start_positions):
        # Find the end of this page div
        # We need to find the matching </div> that closes the page div
        # The structure is: <div class="page"><div class="page-header">...</div><div class="issues">...</div></div>
        # So we look for two consecutive </div> tags
        search_content = content[start_pos:]
        
        # Find the first </div> that closes the page-header (if present)
        # Then find the next </div> that closes the issues div
        # Then find the next </div> that closes the page div
        
        # Count divs to find the matching close
        depth = 1
        pos = 0
        in_page = True
        
        while depth > 0 and pos < len(search_content):
            if search_content[pos:pos+6] == '<div ':
                depth += 1
                pos += 6
            elif search_content[pos:pos+6] == '</div>':
                depth -= 1
                pos += 6
            else:
                pos += 1
        
        if depth == 0:
            page_content = search_content[:pos]
            pages.append(page_content)
    
    print(f"Found {len(pages)} pages to split.")
    
    # Extract page info and create individual files
    page_files = []
    
    for i, page in enumerate(pages, 1):
        # Extract page title and URL
        title_match = re.search(r'<h3>(.*?)</h3>', page)
        url_match = re.search(r'<div class="page-url">(.*?)</div>', page)
        stats_match = re.search(r'<div>Avvik: (\d+) \| Bestått: (\d+)</div>', page)
        
        title = title_match.group(1).strip() if title_match else f"Page {i}"
        url = url_match.group(1) if url_match else ""
        violations = stats_match.group(1) if stats_match else "0"
        passed = stats_match.group(2) if stats_match else "0"
        
        # Create safe filename
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]
        safe_title = safe_title.strip('_')
        
        # If no title, use URL
        if not safe_title or safe_title == '_':
            if url:
                url_parts = url.rstrip('/').split('/')
                safe_title = url_parts[-1] if url_parts else f"page_{i}"
            else:
                safe_title = f"page_{i}"
        
        filename = f"page_{i:02d}_{safe_title}.html"
        page_files.append((filename, title, url, violations, passed))
        
        # Create the individual page HTML
        page_html = f'''<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WCAG Report - {title}</title>
    <style>
        {get_common_styles()}
    </style>
</head>
<body>
    <div class="header">
        <h1>WCAG 2.1 Tilgjengelighetsrapport</h1>
        <p>Side: {title}</p>
        <p><strong>URL:</strong> <a href="{url}">{url}</a></p>
        <p><strong>Dato:</strong> 2026-01-06</p>
        <p><a href="index.html">← Tilbake til oversikt</a></p>
    </div>
    
    <div class="summary">
        <div class="stat">
            <div class="stat-value">{violations}</div>
            <div class="stat-label">Avvik</div>
        </div>
        <div class="stat passed">
            <div class="stat-value">{passed}</div>
            <div class="stat-label">Bestått</div>
        </div>
    </div>
    
    {page}
    
    <div class="footer">
        <p><a href="index.html">← Tilbake til oversikt</a></p>
    </div>
</body>
</html>'''
        
        # Write the page file
        page_path = output_dir / filename
        with open(page_path, 'w', encoding='utf-8') as f:
            f.write(page_html)
        print(f"  Created: {filename}")
    
    # Create index file
    index_html = f'''<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WCAG 2.1 Tilgjengelighetsrapport - Oversikt</title>
    <style>
        {get_common_styles()}
        .page-list {{ list-style: none; padding: 0; }}
        .page-list li {{ margin: 10px 0; padding: 15px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .page-list a {{ text-decoration: none; color: #003366; font-weight: 500; }}
        .page-list a:hover {{ text-decoration: underline; }}
        .page-stats {{ color: #666; font-size: 0.9em; margin-top: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>WCAG 2.1 Tilgjengelighetsrapport</h1>
        <p>Hasvik Kommune - https://www.hasvik.kommune.no/</p>
        <p><strong>Dato:</strong> 2026-01-06</p>
    </div>
    
    <h2>Resultater per side ({len(pages)} sider)</h2>
    
    <ul class="page-list">
'''
    
    for filename, title, url, violations, passed in page_files:
        index_html += f'''        <li>
            <a href="{filename}">{title}</a>
            <div class="page-stats">Avvik: {violations} | Bestått: {passed}</div>
            <div class="page-url"><a href="{url}" target="_blank">{url}</a></div>
        </li>
'''
    
    index_html += '''    </ul>
    
    <div class="footer">
        <p>Generert av WCAG Checker</p>
    </div>
</body>
</html>'''
    
    # Write index file
    index_path = output_dir / 'index.html'
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_html)
    print(f"\nCreated index file: index.html")
    print(f"\nTotal pages: {len(pages)}")
    print(f"Output directory: {output_dir.absolute()}")

def get_common_styles():
    """Return common CSS styles for the reports."""
    return '''
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               line-height: 1.6; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        h1, h2, h3 { color: #1a1a2e; }
        .header { background: #003366; color: white; padding: 30px; border-radius: 8px; margin-bottom: 20px; }
        .header h1 { margin: 0; color: white; }
        .header p { margin: 10px 0 0 0; opacity: 0.9; }
        .header a { color: white; text-decoration: underline; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); 
                   gap: 15px; margin: 20px 0; }
        .stat { background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stat-value { font-size: 2em; font-weight: bold; }
        .stat-label { color: #666; }
        .critical { background: #fee; color: #c00; }
        .serious { background: #fff3e0; color: #e65100; }
        .moderate { background: #fff8e1; color: #f9a825; }
        .minor { background: #e8f5e9; color: #2e7d32; }
        .passed { background: #e8f5e9; }
        .page { background: white; border-radius: 8px; margin: 20px 0; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .page-header { background: #f8f9fa; padding: 15px 20px; border-bottom: 1px solid #ddd; }
        .page-header h3 { margin: 0; }
        .page-url { color: #666; font-size: 0.9em; word-break: break-all; }
        .issues { padding: 20px; }
        .issue { background: #fff; border-left: 4px solid #ccc; padding: 15px; margin: 10px 0; border-radius: 0 4px 4px 0; }
        .issue.critical { border-color: #c00; background: #fff5f5; }
        .issue.serious { border-color: #e65100; background: #fff8f0; }
        .issue.moderate { border-color: #f9a825; background: #fffdf0; }
        .issue.minor { border-color: #2e7d32; background: #f5fff5; }
        .issue-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 10px; }
        .rule-id { font-weight: bold; font-size: 1.1em; color: #003366; }
        .criterion { color: #666; font-size: 0.9em; }
        .impact { padding: 4px 12px; border-radius: 4px; font-size: 0.85em; font-weight: 500; }
        .impact.critical { background: #c00; color: white; }
        .impact.serious { background: #e65100; color: white; }
        .impact.moderate { background: #f9a825; color: #333; }
        .impact.minor { background: #2e7d32; color: white; }
        .element { background: #f5f5f5; padding: 10px; font-family: monospace; 
                   font-size: 0.9em; overflow-x: auto; margin: 10px 0; border-radius: 4px; }
        .fix { background: #e3f2fd; padding: 12px; border-radius: 4px; margin-top: 10px; }
        .fix::before { content: "💡 Løsning: "; font-weight: bold; }
        .no-issues { color: #2e7d32; padding: 20px; text-align: center; font-size: 1.1em; }
        details { margin: 10px 0; }
        summary { cursor: pointer; padding: 12px 15px; background: #f5f5f5; border-radius: 4px; font-weight: 500; }
        summary:hover { background: #eee; }
        .legend { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .legend h3 { margin-top: 0; }
        .legend-items { display: flex; gap: 20px; flex-wrap: wrap; }
        .legend-item { display: flex; align-items: center; gap: 8px; }
        .legend-color { width: 16px; height: 16px; border-radius: 3px; }
        .footer { text-align: center; padding: 20px; color: #666; font-size: 0.9em; }
        .footer a { color: #003366; }
    '''

if __name__ == '__main__':
    input_file = 'wcag_report_20260106_072928.html'
    output_dir = 'wcag_report_pages'
    
    print("Splitting WCAG report into individual page reports...")
    print(f"Input: {input_file}")
    print(f"Output directory: {output_dir}")
    print()
    
    split_wcag_report(input_file, output_dir)
    print("\nDone!")
