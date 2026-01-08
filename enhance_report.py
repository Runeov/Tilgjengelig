#!/usr/bin/env python3
"""
Enhance existing WCAG HTML reports with filtering and rescan capabilities.
Integrates controls directly into the summary stats section.

Usage:
    python enhance_report.py report.html
    python enhance_report.py report.html --output enhanced_report.html
"""

import re
import sys
import argparse
from pathlib import Path


def get_additional_css():
    """Return the additional CSS as a plain string."""
    return """
        /* Enhanced Summary Stats */
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 12px;
            margin: 20px 0;
        }
        .stat {
            background: white;
            padding: 15px 10px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.2s;
            position: relative;
        }
        .stat-value { font-size: 1.8em; font-weight: bold; }
        .stat-label { color: #666; font-size: 0.85em; }
        
        /* Filterable Stats */
        .stat.filterable {
            cursor: pointer;
            border: 3px solid transparent;
            user-select: none;
        }
        .stat.filterable:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .stat.filterable.active {
            border-color: currentColor;
        }
        .stat.filterable::before {
            content: '✓';
            position: absolute;
            top: 6px;
            right: 8px;
            font-size: 12px;
            font-weight: bold;
            opacity: 0;
            transition: opacity 0.2s;
        }
        .stat.filterable.active::before {
            opacity: 1;
        }
        .stat.filterable:not(.active) {
            opacity: 0.4;
            filter: grayscale(50%);
        }
        .stat.filterable:not(.active):hover {
            opacity: 0.7;
        }
        
        /* Color variants */
        .stat.critical { background: #fee; color: #c00; }
        .stat.critical.active { border-color: #c00; }
        .stat.serious { background: #fff3e0; color: #e65100; }
        .stat.serious.active { border-color: #e65100; }
        .stat.moderate { background: #fff8e1; color: #9e6b00; }
        .stat.moderate.active { border-color: #f9a825; }
        .stat.minor { background: #e8f5e9; color: #2e7d32; }
        .stat.minor.active { border-color: #2e7d32; }
        .stat.passed { background: #e8f5e9; color: #2e7d32; }
        
        /* Pages Tested - Interactive */
        .stat.pages-control {
            background: linear-gradient(135deg, #003366 0%, #004080 100%);
            color: white;
            cursor: pointer;
        }
        .stat.pages-control:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,51,102,0.3);
        }
        .stat.pages-control .stat-value {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }
        .pages-adjust {
            display: flex;
            flex-direction: column;
            gap: 1px;
        }
        .pages-adjust button {
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            width: 22px;
            height: 16px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 9px;
            line-height: 1;
            transition: background 0.2s;
        }
        .pages-adjust button:hover {
            background: rgba(255,255,255,0.4);
        }
        .stat.pages-control .stat-label {
            color: rgba(255,255,255,0.9);
        }
        
        /* Rescan Button */
        .stat.rescan-btn {
            background: #2e7d32;
            color: white;
            cursor: pointer;
        }
        .stat.rescan-btn:hover {
            background: #1b5e20;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(46,125,50,0.3);
        }
        .stat.rescan-btn .stat-value {
            font-size: 1.5em;
        }
        .stat.rescan-btn .stat-label {
            color: rgba(255,255,255,0.9);
        }
        
        /* Filter Status Bar */
        .filter-status {
            background: #f8f9fa;
            padding: 12px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }
        .filter-status-text {
            font-size: 14px;
            color: #666;
        }
        .filter-status-text strong {
            color: #333;
            font-size: 1.1em;
        }
        .filter-actions {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        .filter-action-btn {
            padding: 6px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }
        .filter-action-btn:hover {
            background: #e9e9e9;
            border-color: #999;
        }
        
        /* Issue Filtering */
        .issue.hidden { display: none !important; }
        details.hidden { display: none !important; }
        
        /* Modal */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.6);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            backdrop-filter: blur(2px);
        }
        .modal-overlay.active { display: flex; }
        .modal {
            background: white;
            padding: 30px;
            border-radius: 12px;
            max-width: 520px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            animation: modalIn 0.2s ease-out;
        }
        @keyframes modalIn {
            from { transform: scale(0.95); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
        }
        .modal h3 { 
            margin: 0 0 20px 0; 
            color: #003366;
            font-size: 1.4em;
        }
        .modal-url {
            background: #f5f5f5;
            padding: 12px 15px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 13px;
            word-break: break-all;
            border-left: 4px solid #003366;
        }
        .modal-pages {
            display: flex;
            align-items: center;
            gap: 15px;
            margin: 25px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .modal-pages label {
            font-weight: 600;
            color: #333;
        }
        .modal-pages input {
            width: 80px;
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 18px;
            font-weight: bold;
            text-align: center;
        }
        .modal-pages input:focus {
            border-color: #003366;
            outline: none;
        }
        .modal-pages-hint {
            font-size: 12px;
            color: #888;
        }
        .modal-command {
            background: #1a1a2e;
            color: #4ade80;
            padding: 15px;
            border-radius: 6px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
            margin: 20px 0;
            overflow-x: auto;
        }
        .modal-actions {
            display: flex;
            gap: 12px;
            justify-content: flex-end;
            margin-top: 25px;
        }
        .modal-btn {
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s;
        }
        .modal-btn.secondary {
            background: #f5f5f5;
            color: #333;
        }
        .modal-btn.secondary:hover { background: #e0e0e0; }
        .modal-btn.primary {
            background: #003366;
            color: white;
        }
        .modal-btn.primary:hover { background: #004488; }
    """


def get_javascript(base_url, total_count, pages_count):
    """Return the JavaScript as a plain string with values inserted safely."""
    return """
    <script>
        // Configuration
        var BASE_URL = "%s";
        var TOTAL_ISSUES = %s;
        var maxPages = %s;
        
        // Filter state
        var activeFilters = {
            critical: true,
            serious: true,
            moderate: true,
            minor: true
        };
        
        // Toggle filter
        function toggleFilter(severity) {
            activeFilters[severity] = !activeFilters[severity];
            var stat = document.querySelector('.stat[data-severity="' + severity + '"]');
            if (stat) {
                if (activeFilters[severity]) {
                    stat.classList.add('active');
                } else {
                    stat.classList.remove('active');
                }
            }
            applyFilters();
        }
        
        // Select all filters
        function selectAll() {
            var keys = ['critical', 'serious', 'moderate', 'minor'];
            for (var i = 0; i < keys.length; i++) {
                activeFilters[keys[i]] = true;
                var stat = document.querySelector('.stat[data-severity="' + keys[i] + '"]');
                if (stat) stat.classList.add('active');
            }
            applyFilters();
        }
        
        // Deselect all filters
        function selectNone() {
            var keys = ['critical', 'serious', 'moderate', 'minor'];
            for (var i = 0; i < keys.length; i++) {
                activeFilters[keys[i]] = false;
                var stat = document.querySelector('.stat[data-severity="' + keys[i] + '"]');
                if (stat) stat.classList.remove('active');
            }
            applyFilters();
        }
        
        // Apply current filters
        function applyFilters() {
            var visibleCount = 0;
            var issues = document.querySelectorAll('.issue[data-severity]');
            for (var i = 0; i < issues.length; i++) {
                var issue = issues[i];
                var severity = issue.getAttribute('data-severity');
                var visible = activeFilters[severity];
                if (visible) {
                    issue.classList.remove('hidden');
                    visibleCount++;
                } else {
                    issue.classList.add('hidden');
                }
            }
            
            var details = document.querySelectorAll('details');
            for (var i = 0; i < details.length; i++) {
                var detail = details[i];
                var childIssues = detail.querySelectorAll('.issue[data-severity]');
                var hasVisible = false;
                for (var j = 0; j < childIssues.length; j++) {
                    if (!childIssues[j].classList.contains('hidden')) {
                        hasVisible = true;
                        break;
                    }
                }
                if (hasVisible) {
                    detail.classList.remove('hidden');
                } else {
                    detail.classList.add('hidden');
                }
            }
            
            var countEl = document.getElementById('visibleCount');
            var totalEl = document.getElementById('visibleTotal');
            if (countEl) countEl.textContent = visibleCount;
            if (totalEl) totalEl.textContent = visibleCount;
        }
        
        // Expand all
        function expandAll() {
            var details = document.querySelectorAll('details:not(.hidden)');
            for (var i = 0; i < details.length; i++) {
                details[i].open = true;
            }
        }
        
        // Collapse all
        function collapseAll() {
            var details = document.querySelectorAll('details');
            for (var i = 0; i < details.length; i++) {
                details[i].open = false;
            }
        }
        
        // Adjust pages count
        function adjustPages(delta) {
            maxPages = Math.max(1, Math.min(500, maxPages + delta));
            var pagesEl = document.getElementById('pagesValue');
            var inputEl = document.getElementById('maxPages');
            if (pagesEl) pagesEl.textContent = maxPages;
            if (inputEl) inputEl.value = maxPages;
            updateCommand();
        }
        
        // Show rescan modal
        function showRescanModal() {
            var modal = document.getElementById('rescanModal');
            var inputEl = document.getElementById('maxPages');
            if (modal) modal.classList.add('active');
            if (inputEl) inputEl.value = maxPages;
            updateCommand();
        }
        
        // Close rescan modal
        function closeRescanModal() {
            var modal = document.getElementById('rescanModal');
            if (modal) modal.classList.remove('active');
        }
        
        // Update command
        function updateCommand() {
            var inputEl = document.getElementById('maxPages');
            if (inputEl) {
                maxPages = Math.max(1, Math.min(500, parseInt(inputEl.value) || 10));
                inputEl.value = maxPages;
            }
            var pagesEl = document.getElementById('pagesValue');
            var cmdEl = document.getElementById('rescanCommand');
            if (pagesEl) pagesEl.textContent = maxPages;
            if (cmdEl) cmdEl.textContent = 'python checker.py ' + BASE_URL + ' --max-pages ' + maxPages + ' --format html';
        }
        
        // Copy command
        function copyCommand() {
            var cmdEl = document.getElementById('rescanCommand');
            if (cmdEl && navigator.clipboard) {
                navigator.clipboard.writeText(cmdEl.textContent).then(function() {
                    alert('Kommando kopiert!');
                });
            }
        }
        
        // Close modal on overlay click
        document.addEventListener('click', function(e) {
            if (e.target && e.target.id === 'rescanModal') {
                closeRescanModal();
            }
        });
        
        // Escape key closes modal
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeRescanModal();
        });
    </script>
    """ % (base_url, total_count, pages_count)


def get_new_summary(pages_count, total_count, critical_count, serious_count, moderate_count, minor_count, passed_count):
    """Return the new summary HTML."""
    return """<div class="summary">
        <div class="stat pages-control" onclick="showRescanModal()" title="Klikk for ny skanning">
            <div class="stat-value">
                <span id="pagesValue">%s</span>
                <div class="pages-adjust">
                    <button onclick="event.stopPropagation(); adjustPages(5)" title="+5 sider">▲</button>
                    <button onclick="event.stopPropagation(); adjustPages(-5)" title="-5 sider">▼</button>
                </div>
            </div>
            <div class="stat-label">Sider testet</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="visibleTotal">%s</div>
            <div class="stat-label">Synlige avvik</div>
        </div>
        <div class="stat critical filterable active" data-severity="critical" onclick="toggleFilter('critical')" title="Klikk for å filtrere">
            <div class="stat-value">%s</div>
            <div class="stat-label">Kritiske</div>
        </div>
        <div class="stat serious filterable active" data-severity="serious" onclick="toggleFilter('serious')" title="Klikk for å filtrere">
            <div class="stat-value">%s</div>
            <div class="stat-label">Alvorlige</div>
        </div>
        <div class="stat moderate filterable active" data-severity="moderate" onclick="toggleFilter('moderate')" title="Klikk for å filtrere">
            <div class="stat-value">%s</div>
            <div class="stat-label">Moderate</div>
        </div>
        <div class="stat minor filterable active" data-severity="minor" onclick="toggleFilter('minor')" title="Klikk for å filtrere">
            <div class="stat-value">%s</div>
            <div class="stat-label">Mindre</div>
        </div>
        <div class="stat passed">
            <div class="stat-value">%s</div>
            <div class="stat-label">Bestått</div>
        </div>
        <div class="stat rescan-btn" onclick="showRescanModal()" title="Start ny skanning">
            <div class="stat-value">🔄</div>
            <div class="stat-label">Skann på nytt</div>
        </div>
    </div>
    
    <div class="filter-status">
        <div class="filter-status-text">
            Viser <strong id="visibleCount">%s</strong> av %s avvik
        </div>
        <div class="filter-actions">
            <button class="filter-action-btn" onclick="selectAll()">✓ Alle på</button>
            <button class="filter-action-btn" onclick="selectNone()">✗ Alle av</button>
            <button class="filter-action-btn" onclick="expandAll()">📂 Utvid</button>
            <button class="filter-action-btn" onclick="collapseAll()">📁 Lukk</button>
        </div>
    </div>""" % (pages_count, total_count, critical_count, serious_count, moderate_count, minor_count, passed_count, total_count, total_count)


def get_modal_html(base_url, pages_count):
    """Return the modal HTML."""
    return """
    <!-- Rescan Modal -->
    <div class="modal-overlay" id="rescanModal">
        <div class="modal">
            <h3>🔄 Start ny skanning</h3>
            <div class="modal-url">%s</div>
            <div class="modal-pages">
                <label for="maxPages">Antall sider:</label>
                <input type="number" id="maxPages" value="%s" min="1" max="500" onchange="updateCommand()">
                <span class="modal-pages-hint">1-500 sider</span>
            </div>
            <p style="font-size: 13px; color: #666; margin: 0 0 8px 0;">
                Kopier og kjør denne kommandoen i terminalen:
            </p>
            <div class="modal-command" id="rescanCommand">python checker.py %s --max-pages %s --format html</div>
            <div class="modal-actions">
                <button class="modal-btn secondary" onclick="closeRescanModal()">Lukk</button>
                <button class="modal-btn primary" onclick="copyCommand()">📋 Kopier kommando</button>
            </div>
        </div>
    </div>
    """ % (base_url, pages_count, base_url, pages_count)


def inject_enhanced_features(html_content):
    """Inject enhanced CSS and JavaScript into existing report."""
    
    # Inject CSS before </style>
    additional_css = get_additional_css()
    html_content = html_content.replace('</style>', additional_css + '\n    </style>')
    
    # Extract counts from the report
    critical_match = re.search(r'<div class="stat-value">(\d+)</div>\s*<div class="stat-label">Kritiske', html_content)
    serious_match = re.search(r'<div class="stat-value">(\d+)</div>\s*<div class="stat-label">Alvorlige', html_content)
    moderate_match = re.search(r'<div class="stat-value">(\d+)</div>\s*<div class="stat-label">Moderate', html_content)
    minor_match = re.search(r'<div class="stat-value">(\d+)</div>\s*<div class="stat-label">Mindre', html_content)
    total_match = re.search(r'<div class="stat-value">(\d+)</div>\s*<div class="stat-label">Totalt avvik', html_content)
    pages_match = re.search(r'<div class="stat-value">(\d+)</div>\s*<div class="stat-label">Sider testet', html_content)
    passed_match = re.search(r'<div class="stat-value">(\d+)</div>\s*<div class="stat-label">Bestått', html_content)
    
    critical_count = critical_match.group(1) if critical_match else "0"
    serious_count = serious_match.group(1) if serious_match else "0"
    moderate_count = moderate_match.group(1) if moderate_match else "0"
    minor_count = minor_match.group(1) if minor_match else "0"
    total_count = total_match.group(1) if total_match else "0"
    pages_count = pages_match.group(1) if pages_match else "10"
    passed_count = passed_match.group(1) if passed_match else "0"
    
    # Extract base URL
    url_match = re.search(r'<strong>Nettsted:</strong>\s*([^\s<]+)', html_content)
    base_url = url_match.group(1) if url_match else "https://example.com"
    
    # Get new summary HTML
    new_summary = get_new_summary(pages_count, total_count, critical_count, serious_count, moderate_count, minor_count, passed_count)
    
    # Replace existing summary section
    summary_pattern = r'<div class="summary">[\s\S]*?</div>\s*\n\s*<h2>Resultater'
    replacement = new_summary + '\n    <h2>Resultater'
    html_content = re.sub(summary_pattern, replacement, html_content)
    
    # Add data-severity attribute to all issues
    html_content = re.sub(r'<div class="issue critical">', '<div class="issue critical" data-severity="critical">', html_content)
    html_content = re.sub(r'<div class="issue serious">', '<div class="issue serious" data-severity="serious">', html_content)
    html_content = re.sub(r'<div class="issue moderate">', '<div class="issue moderate" data-severity="moderate">', html_content)
    html_content = re.sub(r'<div class="issue minor">', '<div class="issue minor" data-severity="minor">', html_content)
    
    # Get modal HTML and JavaScript
    modal_html = get_modal_html(base_url, pages_count)
    javascript = get_javascript(base_url, total_count, pages_count)
    
    # Inject before </body>
    injection = modal_html + javascript
    html_content = re.sub(r'</body>', injection + '\n</body>', html_content, flags=re.IGNORECASE)
    
    return html_content


def main():
    parser = argparse.ArgumentParser(description='Enhance WCAG HTML reports with filtering capabilities')
    parser.add_argument('input', help='Input HTML report file')
    parser.add_argument('--output', '-o', help='Output file (default: input_enhanced.html)')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {args.input}")
        sys.exit(1)
    
    # Read input
    with open(input_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Enhance
    enhanced_html = inject_enhanced_features(html_content)
    
    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.parent / f"{input_path.stem}_enhanced{input_path.suffix}"
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(enhanced_html)
    
    print(f"✅ Enhanced report: {output_path}")
    print()
    print("   Nye funksjoner:")
    print("   • Klikk på Kritiske/Alvorlige/Moderate/Mindre for å filtrere")
    print("   • Klikk på 'Sider testet' eller '🔄 Skann på nytt' for ny skanning")
    print("   • Bruk ▲/▼ knappene for å justere antall sider")
    print("   • 'Alle på/av' og 'Utvid/Lukk' hurtigknapper")


if __name__ == "__main__":
    main()
