"""
Enhanced HTML Report Generator for WCAG Checker
Adds filtering, expand/collapse all, rescan button, and better navigation.
"""

def generate_enhanced_html_report(result, site_url=None):
    """
    Generate enhanced HTML report with interactive features.
    
    Args:
        result: SiteResult object with all page results
        site_url: URL for rescan button (optional, defaults to result.base_url)
    
    Returns:
        HTML string
    """
    summary = result.summary
    site_url = site_url or result.base_url
    
    # Count issues by severity across all pages
    severity_counts = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
    for page in result.pages:
        for issue in page.issues:
            impact = getattr(issue, 'impact', 'moderate')
            if impact in severity_counts:
                severity_counts[impact] += 1
    
    html = f"""<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WCAG 2.1 Tilgjengelighetsrapport - {result.base_url}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            line-height: 1.6; 
            max-width: 1400px; 
            margin: 0 auto; 
            padding: 20px; 
            background: #f5f5f5; 
        }}
        h1, h2, h3 {{ color: #1a1a2e; }}
        
        /* Header */
        .header {{ 
            background: linear-gradient(135deg, #003366 0%, #004080 100%); 
            color: white; 
            padding: 30px; 
            border-radius: 8px; 
            margin-bottom: 20px; 
        }}
        .header h1 {{ margin: 0; color: white; }}
        .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
        
        /* Control Bar */
        .control-bar {{
            background: white;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            align-items: center;
        }}
        .control-group {{
            display: flex;
            gap: 8px;
            align-items: center;
            flex-wrap: wrap;
        }}
        .control-label {{
            font-weight: 600;
            color: #333;
            margin-right: 5px;
        }}
        
        /* Filter Buttons */
        .filter-btn {{
            padding: 8px 16px;
            border: 2px solid #ddd;
            border-radius: 20px;
            background: white;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .filter-btn:hover {{ background: #f5f5f5; }}
        .filter-btn.active {{ border-color: #003366; background: #e3f2fd; }}
        .filter-btn.critical {{ border-color: #c00; }}
        .filter-btn.critical.active {{ background: #fee; border-color: #c00; }}
        .filter-btn.serious {{ border-color: #e65100; }}
        .filter-btn.serious.active {{ background: #fff3e0; border-color: #e65100; }}
        .filter-btn.moderate {{ border-color: #f9a825; }}
        .filter-btn.moderate.active {{ background: #fff8e1; border-color: #f9a825; }}
        .filter-btn.minor {{ border-color: #2e7d32; }}
        .filter-btn.minor.active {{ background: #e8f5e9; border-color: #2e7d32; }}
        
        .filter-count {{
            background: #666;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 12px;
        }}
        .filter-btn.critical .filter-count {{ background: #c00; }}
        .filter-btn.serious .filter-count {{ background: #e65100; }}
        .filter-btn.moderate .filter-count {{ background: #f9a825; color: #333; }}
        .filter-btn.minor .filter-count {{ background: #2e7d32; }}
        
        /* Action Buttons */
        .action-btn {{
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s;
        }}
        .action-btn.primary {{
            background: #003366;
            color: white;
        }}
        .action-btn.primary:hover {{ background: #004080; }}
        .action-btn.secondary {{
            background: #f5f5f5;
            color: #333;
            border: 1px solid #ddd;
        }}
        .action-btn.secondary:hover {{ background: #eee; }}
        .action-btn.rescan {{
            background: #2e7d32;
            color: white;
        }}
        .action-btn.rescan:hover {{ background: #1b5e20; }}
        
        /* Statement Section */
        .statement-section {{ 
            background: white; 
            border-radius: 8px; 
            padding: 20px; 
            margin-bottom: 20px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
        }}
        .statement-section h2 {{ margin-top: 0; color: #003366; }}
        .statement-status {{ display: flex; flex-wrap: wrap; gap: 15px; margin-top: 15px; }}
        .statement-item {{ display: flex; align-items: center; gap: 8px; padding: 10px 15px; border-radius: 6px; }}
        .statement-item.success {{ background: #e8f5e9; color: #2e7d32; }}
        .statement-item.warning {{ background: #fff3e0; color: #e65100; }}
        .statement-item.error {{ background: #fee; color: #c00; }}
        .statement-link {{ color: #003366; text-decoration: none; }}
        .statement-link:hover {{ text-decoration: underline; }}
        .statement-details {{ margin-top: 15px; padding: 15px; background: #f8f9fa; border-radius: 6px; }}
        .statement-details p {{ margin: 5px 0; }}
        
        /* Summary Grid */
        .summary {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); 
            gap: 15px; 
            margin: 20px 0; 
        }}
        .stat {{ 
            background: white; 
            padding: 20px; 
            border-radius: 8px; 
            text-align: center; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .stat:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }}
        .stat-value {{ font-size: 2em; font-weight: bold; }}
        .stat-label {{ color: #666; }}
        .stat.critical {{ background: #fee; color: #c00; }}
        .stat.serious {{ background: #fff3e0; color: #e65100; }}
        .stat.moderate {{ background: #fff8e1; color: #f9a825; }}
        .stat.minor {{ background: #e8f5e9; color: #2e7d32; }}
        .stat.passed {{ background: #e8f5e9; }}
        
        /* Page Navigation */
        .page-nav {{
            background: white;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .page-nav h3 {{ margin: 0 0 10px 0; font-size: 14px; color: #666; }}
        .page-nav-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .page-nav-item {{
            padding: 6px 12px;
            background: #f5f5f5;
            border-radius: 4px;
            font-size: 13px;
            color: #333;
            text-decoration: none;
            cursor: pointer;
            transition: background 0.2s;
        }}
        .page-nav-item:hover {{ background: #e0e0e0; }}
        .page-nav-item .issue-count {{
            background: #c00;
            color: white;
            padding: 2px 6px;
            border-radius: 10px;
            font-size: 11px;
            margin-left: 6px;
        }}
        
        /* Page Results */
        .page {{ 
            background: white; 
            border-radius: 8px; 
            margin: 20px 0; 
            overflow: hidden; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
        }}
        .page.hidden {{ display: none; }}
        .page-header {{ 
            background: #f8f9fa; 
            padding: 15px 20px; 
            border-bottom: 1px solid #ddd;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .page-header-left {{ flex: 1; }}
        .page-header h3 {{ margin: 0; }}
        .page-url {{ color: #666; font-size: 0.9em; word-break: break-all; }}
        .page-stats {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .page-stat {{
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }}
        .page-stat.critical {{ background: #fee; color: #c00; }}
        .page-stat.serious {{ background: #fff3e0; color: #e65100; }}
        .page-stat.moderate {{ background: #fff8e1; color: #9e6b00; }}
        .page-stat.minor {{ background: #e8f5e9; color: #2e7d32; }}
        
        .issues {{ padding: 20px; }}
        .issue {{ 
            background: #fff; 
            border-left: 4px solid #ccc; 
            padding: 15px; 
            margin: 10px 0; 
            border-radius: 0 4px 4px 0; 
        }}
        .issue.hidden {{ display: none; }}
        .issue.critical {{ border-color: #c00; background: #fff5f5; }}
        .issue.serious {{ border-color: #e65100; background: #fff8f0; }}
        .issue.moderate {{ border-color: #f9a825; background: #fffdf0; }}
        .issue.minor {{ border-color: #2e7d32; background: #f5fff5; }}
        .issue-header {{ 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            margin-bottom: 10px; 
            flex-wrap: wrap; 
            gap: 10px; 
        }}
        .rule-id {{ font-weight: bold; font-size: 1.1em; color: #003366; }}
        .criterion {{ color: #666; font-size: 0.9em; }}
        .impact {{ padding: 4px 12px; border-radius: 4px; font-size: 0.85em; font-weight: 500; }}
        .impact.critical {{ background: #c00; color: white; }}
        .impact.serious {{ background: #e65100; color: white; }}
        .impact.moderate {{ background: #f9a825; color: #333; }}
        .impact.minor {{ background: #2e7d32; color: white; }}
        .element {{ 
            background: #f5f5f5; 
            padding: 10px; 
            font-family: monospace; 
            font-size: 0.9em; 
            overflow-x: auto; 
            margin: 10px 0; 
            border-radius: 4px; 
        }}
        .fix {{ background: #e3f2fd; padding: 12px; border-radius: 4px; margin-top: 10px; }}
        .fix::before {{ content: "💡 Løsning: "; font-weight: bold; }}
        .no-issues {{ color: #2e7d32; padding: 20px; text-align: center; font-size: 1.1em; }}
        
        /* Details/Summary */
        details {{ margin: 10px 0; }}
        details.hidden {{ display: none; }}
        summary {{ 
            cursor: pointer; 
            padding: 12px 15px; 
            background: #f5f5f5; 
            border-radius: 4px; 
            font-weight: 500;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        summary:hover {{ background: #eee; }}
        summary::marker {{ content: ''; }}
        summary::before {{ 
            content: '▶'; 
            margin-right: 10px; 
            transition: transform 0.2s;
            display: inline-block;
        }}
        details[open] summary::before {{ transform: rotate(90deg); }}
        .summary-badges {{
            display: flex;
            gap: 6px;
        }}
        .summary-badge {{
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 600;
        }}
        .summary-badge.critical {{ background: #c00; color: white; }}
        .summary-badge.serious {{ background: #e65100; color: white; }}
        .summary-badge.moderate {{ background: #f9a825; color: #333; }}
        .summary-badge.minor {{ background: #2e7d32; color: white; }}
        
        /* Legend */
        .legend {{ 
            background: white; 
            padding: 20px; 
            border-radius: 8px; 
            margin-bottom: 20px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
        }}
        .legend h3 {{ margin-top: 0; }}
        .legend-items {{ display: flex; gap: 20px; flex-wrap: wrap; }}
        .legend-item {{ display: flex; align-items: center; gap: 8px; }}
        .legend-color {{ width: 16px; height: 16px; border-radius: 3px; }}
        
        /* Footer */
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 0.9em; }}
        .footer a {{ color: #003366; }}
        
        /* Visible count */
        .visible-count {{
            background: #f5f5f5;
            padding: 10px 15px;
            border-radius: 6px;
            font-size: 14px;
            color: #666;
        }}
        .visible-count strong {{ color: #333; }}
        
        /* Rescan Modal */
        .modal-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }}
        .modal-overlay.active {{ display: flex; }}
        .modal {{
            background: white;
            padding: 30px;
            border-radius: 12px;
            max-width: 500px;
            width: 90%;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        .modal h3 {{ margin-top: 0; }}
        .modal-input {{
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            margin: 15px 0;
        }}
        .modal-input:focus {{ border-color: #003366; outline: none; }}
        .modal-actions {{
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>WCAG 2.1 Tilgjengelighetsrapport</h1>
        <p>Basert på testregler fra Tilsynet for universell utforming av IKT</p>
        <p><strong>Nettsted:</strong> {result.base_url}</p>
        <p><strong>Dato:</strong> {result.timestamp}</p>
    </div>
    
    <!-- Control Bar -->
    <div class="control-bar">
        <div class="control-group">
            <span class="control-label">Filter:</span>
            <button class="filter-btn critical active" data-filter="critical" onclick="toggleFilter('critical')">
                Kritisk <span class="filter-count">{severity_counts['critical']}</span>
            </button>
            <button class="filter-btn serious active" data-filter="serious" onclick="toggleFilter('serious')">
                Alvorlig <span class="filter-count">{severity_counts['serious']}</span>
            </button>
            <button class="filter-btn moderate active" data-filter="moderate" onclick="toggleFilter('moderate')">
                Moderat <span class="filter-count">{severity_counts['moderate']}</span>
            </button>
            <button class="filter-btn minor active" data-filter="minor" onclick="toggleFilter('minor')">
                Mindre <span class="filter-count">{severity_counts['minor']}</span>
            </button>
        </div>
        
        <div class="control-group">
            <button class="action-btn secondary" onclick="expandAll()">📂 Vis alle</button>
            <button class="action-btn secondary" onclick="collapseAll()">📁 Skjul alle</button>
        </div>
        
        <div class="control-group" style="margin-left: auto;">
            <button class="action-btn rescan" onclick="showRescanModal()">🔄 Ny skanning</button>
        </div>
    </div>
    
    <!-- Visible Count -->
    <div class="visible-count" id="visibleCount">
        Viser <strong>{summary['issues']}</strong> av {summary['issues']} avvik
    </div>
"""
    
    # Accessibility statement section (if available)
    if hasattr(result, 'accessibility_statement') and result.accessibility_statement:
        stmt = result.accessibility_statement
        html += f"""
    <div class="statement-section">
        <h2>📋 Tilgjengelighetserklæring Status</h2>
        <div class="statement-status">
"""
        if stmt.has_statement_page:
            html += """
            <div class="statement-item success">
                ✅ <strong>Tilgjengelighetserklæring funnet</strong>
            </div>
"""
        else:
            html += """
            <div class="statement-item error">
                ❌ <strong>Tilgjengelighetserklæring mangler</strong>
            </div>
"""
        if stmt.uustatus_url:
            html += f"""
            <div class="statement-item">
                🔗 <a href="{stmt.uustatus_url}" class="statement-link" target="_blank">Gå til erklæring</a>
            </div>
"""
        html += """
        </div>
    </div>
"""

    # Summary
    html += f"""
    <div class="legend">
        <h3>Alvorlighetsgrad</h3>
        <div class="legend-items">
            <div class="legend-item"><div class="legend-color" style="background:#c00"></div> Kritisk - Blokkerer tilgang</div>
            <div class="legend-item"><div class="legend-color" style="background:#e65100"></div> Alvorlig - Store barrierer</div>
            <div class="legend-item"><div class="legend-color" style="background:#f9a825"></div> Moderat - Betydelige problemer</div>
            <div class="legend-item"><div class="legend-color" style="background:#2e7d32"></div> Mindre - Bør forbedres</div>
        </div>
    </div>
    
    <h2>Sammendrag</h2>
    <div class="summary">
        <div class="stat" onclick="scrollToPage(0)">
            <div class="stat-value">{summary['pages_checked']}</div>
            <div class="stat-label">Sider testet</div>
        </div>
        <div class="stat">
            <div class="stat-value">{summary['issues']}</div>
            <div class="stat-label">Totalt avvik</div>
        </div>
        <div class="stat critical" onclick="filterOnly('critical')">
            <div class="stat-value">{summary['critical']}</div>
            <div class="stat-label">Kritiske</div>
        </div>
        <div class="stat serious" onclick="filterOnly('serious')">
            <div class="stat-value">{summary['serious']}</div>
            <div class="stat-label">Alvorlige</div>
        </div>
        <div class="stat moderate" onclick="filterOnly('moderate')">
            <div class="stat-value">{summary['moderate']}</div>
            <div class="stat-label">Moderate</div>
        </div>
        <div class="stat minor" onclick="filterOnly('minor')">
            <div class="stat-value">{summary['minor']}</div>
            <div class="stat-label">Mindre</div>
        </div>
        <div class="stat passed">
            <div class="stat-value">{summary['passed']}</div>
            <div class="stat-label">Bestått</div>
        </div>
    </div>
"""
    
    # Page Navigation
    html += """
    <div class="page-nav">
        <h3>HURTIGNAVIGASJON TIL SIDER</h3>
        <div class="page-nav-list">
"""
    for i, page in enumerate(result.pages):
        page_title = page.title[:40] + "..." if len(page.title) > 40 else page.title
        issue_count = len(page.issues)
        html += f"""
            <a class="page-nav-item" onclick="scrollToPage({i})">
                {page_title}
                <span class="issue-count">{issue_count}</span>
            </a>
"""
    html += """
        </div>
    </div>
    
    <h2>Resultater per side</h2>
"""
    
    # Page results
    for page_idx, page in enumerate(result.pages):
        page_summary = page.summary
        
        # Count by severity for this page
        page_severity = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
        for issue in page.issues:
            impact = getattr(issue, 'impact', 'moderate')
            if impact in page_severity:
                page_severity[impact] += 1
        
        html += f"""
    <div class="page" id="page-{page_idx}">
        <div class="page-header">
            <div class="page-header-left">
                <h3>{page.title}</h3>
                <div class="page-url">{page.url}</div>
            </div>
            <div class="page-stats">
"""
        if page_severity["critical"] > 0:
            html += f'<span class="page-stat critical">{page_severity["critical"]} kritiske</span>'
        if page_severity["serious"] > 0:
            html += f'<span class="page-stat serious">{page_severity["serious"]} alvorlige</span>'
        if page_severity["moderate"] > 0:
            html += f'<span class="page-stat moderate">{page_severity["moderate"]} moderate</span>'
        if page_severity["minor"] > 0:
            html += f'<span class="page-stat minor">{page_severity["minor"]} mindre</span>'
        
        html += f"""
            </div>
        </div>
        <div class="issues">
"""
        if not page.issues:
            html += '<div class="no-issues">✅ Ingen avvik funnet på denne siden!</div>'
        else:
            # Group by criterion
            by_criterion = {}
            for issue in page.issues:
                key = f"{issue.criterion_id} {issue.criterion_name}"
                if key not in by_criterion:
                    by_criterion[key] = []
                by_criterion[key].append(issue)
            
            for criterion, issues in by_criterion.items():
                # Count by severity for this criterion
                criterion_severity = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
                for issue in issues:
                    impact = getattr(issue, 'impact', 'moderate')
                    if impact in criterion_severity:
                        criterion_severity[impact] += 1
                
                # Build severity badges string
                badges = ""
                if criterion_severity["critical"] > 0:
                    badges += f'<span class="summary-badge critical">{criterion_severity["critical"]} kritisk</span>'
                if criterion_severity["serious"] > 0:
                    badges += f'<span class="summary-badge serious">{criterion_severity["serious"]} alvorlig</span>'
                if criterion_severity["moderate"] > 0:
                    badges += f'<span class="summary-badge moderate">{criterion_severity["moderate"]} moderat</span>'
                if criterion_severity["minor"] > 0:
                    badges += f'<span class="summary-badge minor">{criterion_severity["minor"]} mindre</span>'
                
                # Data attributes for filtering
                severity_classes = []
                if criterion_severity["critical"] > 0:
                    severity_classes.append("has-critical")
                if criterion_severity["serious"] > 0:
                    severity_classes.append("has-serious")
                if criterion_severity["moderate"] > 0:
                    severity_classes.append("has-moderate")
                if criterion_severity["minor"] > 0:
                    severity_classes.append("has-minor")
                
                html += f'<details class="{" ".join(severity_classes)}" open>'
                html += f'<summary><span>{criterion} ({len(issues)} avvik)</span><span class="summary-badges">{badges}</span></summary>'
                
                for issue in issues:
                    element_escaped = issue.element.replace('<', '&lt;').replace('>', '&gt;')
                    rule_id = getattr(issue, 'rule_id', issue.criterion_id)
                    impact = getattr(issue, 'impact', 'moderate')
                    
                    html += f"""
            <div class="issue {impact}" data-severity="{impact}">
                <div class="issue-header">
                    <div>
                        <span class="rule-id">Testregel {rule_id}</span>
                        <span class="criterion">({issue.criterion_id} - Nivå {issue.level})</span>
                    </div>
                    <span class="impact {impact}">{impact.upper()}</span>
                </div>
                <p>{issue.issue}</p>
                <div class="element">{element_escaped}</div>
                <div class="fix">{issue.fix}</div>
            </div>
"""
                html += '</details>'
        
        html += """
        </div>
    </div>
"""
    
    # Footer and JavaScript
    html += f"""
    <div class="footer">
        <p>Testreglene er basert på <a href="https://www.uutilsynet.no/regelverk/oversikt-over-testregler-nettsteder/709" target="_blank">UU-tilsynets offisielle testregler</a></p>
    </div>
    
    <!-- Rescan Modal -->
    <div class="modal-overlay" id="rescanModal">
        <div class="modal">
            <h3>🔄 Start ny skanning</h3>
            <p>Skriv inn URL-en du vil skanne:</p>
            <input type="text" class="modal-input" id="rescanUrl" value="{result.base_url}" placeholder="https://example.com">
            <p style="font-size: 13px; color: #666;">
                Kopier og kjør denne kommandoen i terminalen:
            </p>
            <div class="element" id="rescanCommand" style="font-size: 12px;">
                python checker.py {result.base_url} --max-pages 20 --format html
            </div>
            <div class="modal-actions">
                <button class="action-btn secondary" onclick="closeRescanModal()">Avbryt</button>
                <button class="action-btn primary" onclick="copyCommand()">📋 Kopier kommando</button>
            </div>
        </div>
    </div>
    
    <script>
        // Filter state
        const activeFilters = {{
            critical: true,
            serious: true,
            moderate: true,
            minor: true
        }};
        
        // Toggle individual filter
        function toggleFilter(severity) {{
            activeFilters[severity] = !activeFilters[severity];
            
            // Update button state
            const btn = document.querySelector(`[data-filter="${{severity}}"]`);
            btn.classList.toggle('active', activeFilters[severity]);
            
            applyFilters();
        }}
        
        // Filter to show only one severity
        function filterOnly(severity) {{
            // Turn off all filters
            Object.keys(activeFilters).forEach(key => {{
                activeFilters[key] = false;
                document.querySelector(`[data-filter="${{key}}"]`).classList.remove('active');
            }});
            
            // Turn on selected filter
            activeFilters[severity] = true;
            document.querySelector(`[data-filter="${{severity}}"]`).classList.add('active');
            
            applyFilters();
        }}
        
        // Apply current filters to all issues
        function applyFilters() {{
            let visibleCount = 0;
            const totalCount = {summary['issues']};
            
            // Filter individual issues
            document.querySelectorAll('.issue[data-severity]').forEach(issue => {{
                const severity = issue.dataset.severity;
                const visible = activeFilters[severity];
                issue.classList.toggle('hidden', !visible);
                if (visible) visibleCount++;
            }});
            
            // Update details visibility based on whether they have visible issues
            document.querySelectorAll('details').forEach(detail => {{
                const hasVisible = Array.from(detail.querySelectorAll('.issue[data-severity]'))
                    .some(issue => !issue.classList.contains('hidden'));
                detail.classList.toggle('hidden', !hasVisible);
            }});
            
            // Update visible count display
            document.getElementById('visibleCount').innerHTML = 
                `Viser <strong>${{visibleCount}}</strong> av ${{totalCount}} avvik`;
        }}
        
        // Expand all details
        function expandAll() {{
            document.querySelectorAll('details:not(.hidden)').forEach(d => d.open = true);
        }}
        
        // Collapse all details
        function collapseAll() {{
            document.querySelectorAll('details').forEach(d => d.open = false);
        }}
        
        // Scroll to page
        function scrollToPage(index) {{
            const page = document.getElementById(`page-${{index}}`);
            if (page) {{
                page.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            }}
        }}
        
        // Rescan modal
        function showRescanModal() {{
            document.getElementById('rescanModal').classList.add('active');
            updateRescanCommand();
        }}
        
        function closeRescanModal() {{
            document.getElementById('rescanModal').classList.remove('active');
        }}
        
        function updateRescanCommand() {{
            const url = document.getElementById('rescanUrl').value;
            document.getElementById('rescanCommand').textContent = 
                `python checker.py ${{url}} --max-pages 20 --format html`;
        }}
        
        document.getElementById('rescanUrl').addEventListener('input', updateRescanCommand);
        
        function copyCommand() {{
            const command = document.getElementById('rescanCommand').textContent;
            navigator.clipboard.writeText(command).then(() => {{
                alert('Kommando kopiert til utklippstavlen!');
            }});
        }}
        
        // Close modal on overlay click
        document.getElementById('rescanModal').addEventListener('click', function(e) {{
            if (e.target === this) closeRescanModal();
        }});
        
        // Keyboard shortcut (Escape to close modal)
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') closeRescanModal();
        }});
    </script>
</body>
</html>
"""
    return html


# If this file is imported, provide the function
if __name__ == "__main__":
    print("This module provides generate_enhanced_html_report() function")
    print("Import it in your checker.py to use the enhanced report format")
