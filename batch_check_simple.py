#!/usr/bin/env python3
"""
WCAG Checker - Simple Batch script for Norwegian municipalities.
Runs checks directly (no subprocess) to avoid Windows encoding issues.
Generates enhanced reports with filtering and rescan capabilities.
"""

import csv
import sys
import os
import json
import re
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Configuration
CSV_PATH = os.path.join(SCRIPT_DIR, "counties.csv")
OUTPUT_BASE = os.path.join(SCRIPT_DIR, "reports")  # Base folder for all reports

# Default parameters
DEFAULT_MAX_PAGES = 20
DEFAULT_EXCLUDE_PATTERNS = ['/aktuelt/', '/nyheter/', '/artikkel/', '/innhold/', 
                           '/kunngjoring/', '/arrangement/', '/hendelse/', '/dokument/', '/fil/']


# =============================================================================
# REPORT ENHANCEMENT FUNCTIONS
# =============================================================================

def get_enhancement_css():
    """Return the additional CSS for enhanced reports."""
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
        
        .stat.filterable {
            cursor: pointer;
            border: 3px solid transparent;
            user-select: none;
        }
        .stat.filterable:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .stat.filterable.active { border-color: currentColor; }
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
        .stat.filterable.active::before { opacity: 1; }
        .stat.filterable:not(.active) { opacity: 0.4; filter: grayscale(50%); }
        .stat.filterable:not(.active):hover { opacity: 0.7; }
        
        .stat.critical { background: #fee; color: #c00; }
        .stat.critical.active { border-color: #c00; }
        .stat.serious { background: #fff3e0; color: #e65100; }
        .stat.serious.active { border-color: #e65100; }
        .stat.moderate { background: #fff8e1; color: #9e6b00; }
        .stat.moderate.active { border-color: #f9a825; }
        .stat.minor { background: #e8f5e9; color: #2e7d32; }
        .stat.minor.active { border-color: #2e7d32; }
        .stat.passed { background: #e8f5e9; color: #2e7d32; }
        
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
        .pages-adjust { display: flex; flex-direction: column; gap: 1px; }
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
        .pages-adjust button:hover { background: rgba(255,255,255,0.4); }
        .stat.pages-control .stat-label { color: rgba(255,255,255,0.9); }
        
        .stat.rescan-btn { background: #2e7d32; color: white; cursor: pointer; }
        .stat.rescan-btn:hover {
            background: #1b5e20;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(46,125,50,0.3);
        }
        .stat.rescan-btn .stat-value { font-size: 1.5em; }
        .stat.rescan-btn .stat-label { color: rgba(255,255,255,0.9); }
        
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
        .filter-status-text { font-size: 14px; color: #666; }
        .filter-status-text strong { color: #333; font-size: 1.1em; }
        .filter-actions { display: flex; gap: 8px; flex-wrap: wrap; }
        .filter-action-btn {
            padding: 6px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }
        .filter-action-btn:hover { background: #e9e9e9; border-color: #999; }
        
        .issue.hidden { display: none !important; }
        details.hidden { display: none !important; }
        
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
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
        }
        .modal h3 { margin: 0 0 20px 0; color: #003366; font-size: 1.4em; }
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
        .modal-pages label { font-weight: 600; color: #333; }
        .modal-pages input {
            width: 80px;
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 18px;
            font-weight: bold;
            text-align: center;
        }
        .modal-pages input:focus { border-color: #003366; outline: none; }
        .modal-pages-hint { font-size: 12px; color: #888; }
        .modal-command {
            background: #1a1a2e;
            color: #4ade80;
            padding: 15px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 13px;
            margin: 20px 0;
            overflow-x: auto;
        }
        .modal-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 25px; }
        .modal-btn {
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s;
        }
        .modal-btn.secondary { background: #f5f5f5; color: #333; }
        .modal-btn.secondary:hover { background: #e0e0e0; }
        .modal-btn.primary { background: #003366; color: white; }
        .modal-btn.primary:hover { background: #004488; }
    """


def get_enhancement_js(base_url, total_count, pages_count):
    """Return the JavaScript for enhanced reports."""
    return """
    <script>
        var BASE_URL = "%s";
        var TOTAL_ISSUES = %s;
        var maxPages = %s;
        var activeFilters = { critical: true, serious: true, moderate: true, minor: true };
        var isServerMode = false;
        
        // Check if running via server (can make API calls)
        function checkServerMode() {
            var serverModeEl = document.getElementById('serverMode');
            var standaloneModeEl = document.getElementById('standaloneMode');
            
            var xhr = new XMLHttpRequest();
            xhr.open('GET', '/api/reports', true);
            xhr.timeout = 2000;
            xhr.onload = function() {
                if (xhr.status === 200) {
                    isServerMode = true;
                    console.log('Server mode enabled');
                    if (serverModeEl) serverModeEl.style.display = 'block';
                    if (standaloneModeEl) standaloneModeEl.style.display = 'none';
                }
            };
            xhr.onerror = function() { console.log('Standalone mode'); };
            xhr.ontimeout = function() { console.log('Standalone mode (timeout)'); };
            try { xhr.send(); } catch(e) { console.log('Standalone mode'); }
        }
        
        // Run on page load
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', checkServerMode);
        } else {
            checkServerMode();
        }
        
        function toggleFilter(severity) {
            activeFilters[severity] = !activeFilters[severity];
            var stat = document.querySelector('.stat[data-severity="' + severity + '"]');
            if (stat) {
                if (activeFilters[severity]) { stat.classList.add('active'); }
                else { stat.classList.remove('active'); }
            }
            applyFilters();
        }
        
        function selectAll() {
            var keys = ['critical', 'serious', 'moderate', 'minor'];
            for (var i = 0; i < keys.length; i++) {
                activeFilters[keys[i]] = true;
                var stat = document.querySelector('.stat[data-severity="' + keys[i] + '"]');
                if (stat) stat.classList.add('active');
            }
            applyFilters();
        }
        
        function selectNone() {
            var keys = ['critical', 'serious', 'moderate', 'minor'];
            for (var i = 0; i < keys.length; i++) {
                activeFilters[keys[i]] = false;
                var stat = document.querySelector('.stat[data-severity="' + keys[i] + '"]');
                if (stat) stat.classList.remove('active');
            }
            applyFilters();
        }
        
        function applyFilters() {
            var visibleCount = 0;
            var issues = document.querySelectorAll('.issue[data-severity]');
            for (var i = 0; i < issues.length; i++) {
                var issue = issues[i];
                var severity = issue.getAttribute('data-severity');
                if (activeFilters[severity]) {
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
                    if (!childIssues[j].classList.contains('hidden')) { hasVisible = true; break; }
                }
                if (hasVisible) { detail.classList.remove('hidden'); }
                else { detail.classList.add('hidden'); }
            }
            var countEl = document.getElementById('visibleCount');
            var totalEl = document.getElementById('visibleTotal');
            if (countEl) countEl.textContent = visibleCount;
            if (totalEl) totalEl.textContent = visibleCount;
        }
        
        function expandAll() {
            var details = document.querySelectorAll('details:not(.hidden)');
            for (var i = 0; i < details.length; i++) { details[i].open = true; }
        }
        
        function collapseAll() {
            var details = document.querySelectorAll('details');
            for (var i = 0; i < details.length; i++) { details[i].open = false; }
        }
        
        function adjustPages(delta) {
            maxPages = Math.max(1, Math.min(500, maxPages + delta));
            var pagesEl = document.getElementById('pagesValue');
            var inputEl = document.getElementById('maxPages');
            if (pagesEl) pagesEl.textContent = maxPages;
            if (inputEl) inputEl.value = maxPages;
            updateCommand();
        }
        
        function showRescanModal() {
            var modal = document.getElementById('rescanModal');
            var inputEl = document.getElementById('maxPages');
            if (modal) modal.classList.add('active');
            if (inputEl) inputEl.value = maxPages;
            
            // Reset to form view
            var scanForm = document.getElementById('scanForm');
            var scanStatus = document.getElementById('scanStatus');
            var scanComplete = document.getElementById('scanCompleteActions');
            if (scanForm) scanForm.style.display = 'block';
            if (scanStatus) scanStatus.style.display = 'none';
            if (scanComplete) scanComplete.style.display = 'none';
            
            // Re-check server mode
            checkServerMode();
            updateCommand();
        }
        
        function closeRescanModal() {
            var modal = document.getElementById('rescanModal');
            if (modal) modal.classList.remove('active');
        }
        
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
        
        function copyCommand() {
            var cmdEl = document.getElementById('rescanCommand');
            if (cmdEl && navigator.clipboard) {
                navigator.clipboard.writeText(cmdEl.textContent).then(function() { alert('Kommando kopiert!'); });
            }
        }
        
        // Live scan functions (server mode)
        function getCurrentFolder() {
            // Detect folder from current URL path like /reports/20260108_130746/wcag_...
            var path = window.location.pathname;
            var match = path.match(/\/reports\/([^\/]+)\//);
            return match ? match[1] : '';
        }
        
        function startLiveScan() {
            var inputEl = document.getElementById('maxPages');
            var pages = parseInt(inputEl.value) || 20;
            var folder = getCurrentFolder();
            
            var scanForm = document.getElementById('scanForm');
            var scanStatus = document.getElementById('scanStatus');
            var scanProgress = document.getElementById('scanProgress');
            var scanMessage = document.getElementById('scanMessage');
            var scanComplete = document.getElementById('scanCompleteActions');
            
            if (scanForm) scanForm.style.display = 'none';
            if (scanStatus) scanStatus.style.display = 'block';
            if (scanProgress) scanProgress.style.width = '0%%';
            if (scanMessage) scanMessage.textContent = 'Starter skanning...';
            if (scanComplete) scanComplete.style.display = 'none';
            
            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/scan/start', true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.onload = function() {
                if (xhr.status === 200) {
                    var data = JSON.parse(xhr.responseText);
                    if (data.scan_id) {
                        pollScanStatus(data.scan_id);
                    } else {
                        if (scanMessage) scanMessage.textContent = 'Feil: ' + (data.error || 'Ukjent feil');
                        if (scanComplete) scanComplete.style.display = 'flex';
                    }
                } else {
                    if (scanMessage) scanMessage.textContent = 'Feil: Kunne ikke starte skanning';
                    if (scanComplete) scanComplete.style.display = 'flex';
                }
            };
            xhr.onerror = function() {
                if (scanMessage) scanMessage.textContent = 'Feil: Nettverksfeil';
                if (scanComplete) scanComplete.style.display = 'flex';
            };
            var payload = { url: BASE_URL, max_pages: pages };
            if (folder) payload.output_folder = folder;
            xhr.send(JSON.stringify(payload));
        }
        
        function pollScanStatus(scanId) {
            var xhr = new XMLHttpRequest();
            xhr.open('GET', '/api/scan/status?id=' + scanId, true);
            xhr.onload = function() {
                if (xhr.status === 200) {
                    var data = JSON.parse(xhr.responseText);
                    var scanProgress = document.getElementById('scanProgress');
                    var scanMessage = document.getElementById('scanMessage');
                    var scanComplete = document.getElementById('scanCompleteActions');
                    var openReportBtn = document.getElementById('openReportBtn');
                    
                    if (scanProgress) scanProgress.style.width = data.progress + '%%';
                    if (scanMessage) scanMessage.textContent = data.message;
                    
                    if (data.status === 'complete') {
                        if (scanMessage) scanMessage.textContent = 'Ferdig! Rapporten er klar.';
                        if (scanComplete) scanComplete.style.display = 'flex';
                        if (openReportBtn) {
                            openReportBtn.onclick = function() {
                                window.location.href = '/' + data.output_file;
                            };
                        }
                    } else if (data.status === 'error') {
                        if (scanMessage) scanMessage.textContent = 'Feil: ' + data.error;
                        if (scanComplete) scanComplete.style.display = 'flex';
                        if (openReportBtn) openReportBtn.style.display = 'none';
                    } else {
                        setTimeout(function() { pollScanStatus(scanId); }, 1000);
                    }
                }
            };
            xhr.send();
        }
        
        document.addEventListener('click', function(e) {
            if (e.target && e.target.id === 'rescanModal') closeRescanModal();
        });
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeRescanModal();
        });
    </script>
    """ % (base_url, total_count, pages_count)


def enhance_report(html_content):
    """Enhance an HTML report with filtering and rescan capabilities."""
    
    # Extract counts
    critical_match = re.search(r'<div class="stat-value">(\d+)</div>\s*<div class="stat-label">Kritiske', html_content)
    serious_match = re.search(r'<div class="stat-value">(\d+)</div>\s*<div class="stat-label">Alvorlige', html_content)
    moderate_match = re.search(r'<div class="stat-value">(\d+)</div>\s*<div class="stat-label">Moderate', html_content)
    minor_match = re.search(r'<div class="stat-value">(\d+)</div>\s*<div class="stat-label">Mindre', html_content)
    total_match = re.search(r'<div class="stat-value">(\d+)</div>\s*<div class="stat-label">Totalt avvik', html_content)
    pages_match = re.search(r'<div class="stat-value">(\d+)</div>\s*<div class="stat-label">Sider testet', html_content)
    passed_match = re.search(r'<div class="stat-value">(\d+)</div>\s*<div class="stat-label">Bestått', html_content)
    url_match = re.search(r'<strong>Nettsted:</strong>\s*([^\s<]+)', html_content)
    
    critical = critical_match.group(1) if critical_match else "0"
    serious = serious_match.group(1) if serious_match else "0"
    moderate = moderate_match.group(1) if moderate_match else "0"
    minor = minor_match.group(1) if minor_match else "0"
    total = total_match.group(1) if total_match else "0"
    pages = pages_match.group(1) if pages_match else "10"
    passed = passed_match.group(1) if passed_match else "0"
    base_url = url_match.group(1) if url_match else "https://example.com"
    
    # Inject CSS
    html_content = html_content.replace('</style>', get_enhancement_css() + '\n    </style>')
    
    # Create new summary section
    new_summary = """<div class="summary">
        <div class="stat pages-control" onclick="showRescanModal()" title="Klikk for ny skanning">
            <div class="stat-value">
                <span id="pagesValue">%s</span>
                <div class="pages-adjust">
                    <button onclick="event.stopPropagation(); adjustPages(5)" title="+5">▲</button>
                    <button onclick="event.stopPropagation(); adjustPages(-5)" title="-5">▼</button>
                </div>
            </div>
            <div class="stat-label">Sider testet</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="visibleTotal">%s</div>
            <div class="stat-label">Synlige avvik</div>
        </div>
        <div class="stat critical filterable active" data-severity="critical" onclick="toggleFilter('critical')">
            <div class="stat-value">%s</div>
            <div class="stat-label">Kritiske</div>
        </div>
        <div class="stat serious filterable active" data-severity="serious" onclick="toggleFilter('serious')">
            <div class="stat-value">%s</div>
            <div class="stat-label">Alvorlige</div>
        </div>
        <div class="stat moderate filterable active" data-severity="moderate" onclick="toggleFilter('moderate')">
            <div class="stat-value">%s</div>
            <div class="stat-label">Moderate</div>
        </div>
        <div class="stat minor filterable active" data-severity="minor" onclick="toggleFilter('minor')">
            <div class="stat-value">%s</div>
            <div class="stat-label">Mindre</div>
        </div>
        <div class="stat passed">
            <div class="stat-value">%s</div>
            <div class="stat-label">Bestått</div>
        </div>
        <div class="stat rescan-btn" onclick="showRescanModal()">
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
    </div>""" % (pages, total, critical, serious, moderate, minor, passed, total, total)
    
    # Replace summary section
    html_content = re.sub(
        r'<div class="summary">[\s\S]*?</div>\s*\n\s*<h2>Resultater',
        new_summary + '\n    <h2>Resultater',
        html_content
    )
    
    # Add data-severity to issues
    html_content = re.sub(r'<div class="issue critical">', '<div class="issue critical" data-severity="critical">', html_content)
    html_content = re.sub(r'<div class="issue serious">', '<div class="issue serious" data-severity="serious">', html_content)
    html_content = re.sub(r'<div class="issue moderate">', '<div class="issue moderate" data-severity="moderate">', html_content)
    html_content = re.sub(r'<div class="issue minor">', '<div class="issue minor" data-severity="minor">', html_content)
    
    # Add modal and JavaScript
    modal_html = """
    <div class="modal-overlay" id="rescanModal">
        <div class="modal">
            <h3>🔄 Skann på nytt</h3>
            
            <div id="scanForm">
                <div class="modal-url">%s</div>
                <div class="modal-pages">
                    <label>Antall sider:</label>
                    <input type="number" id="maxPages" value="%s" min="1" max="500" onchange="updateCommand()">
                    <span class="modal-pages-hint">Flere sider = grundigere, men tregere</span>
                </div>
                
                <div id="serverMode" style="display:none;">
                    <div class="modal-actions">
                        <button class="modal-btn secondary" onclick="closeRescanModal()">Avbryt</button>
                        <button class="modal-btn primary" onclick="startLiveScan()">▶ Start skanning</button>
                    </div>
                </div>
                
                <div id="standaloneMode">
                    <p style="font-size:13px;color:#666;margin:15px 0 8px">Kopier og kjør i terminal:</p>
                    <div class="modal-command" id="rescanCommand">python checker.py %s --max-pages %s --format html</div>
                    <div class="modal-actions">
                        <button class="modal-btn secondary" onclick="closeRescanModal()">Lukk</button>
                        <button class="modal-btn primary" onclick="copyCommand()">📋 Kopier kommando</button>
                    </div>
                </div>
            </div>
            
            <div id="scanStatus" style="display: none;">
                <div style="background: #f0f0f0; border-radius: 8px; height: 24px; margin: 20px 0; overflow: hidden;">
                    <div id="scanProgress" style="background: linear-gradient(90deg, #003366, #004488); height: 100%%; width: 0%%; transition: width 0.3s;"></div>
                </div>
                <p id="scanMessage" style="text-align: center; color: #666;">Starter...</p>
                <div class="modal-actions" id="scanCompleteActions" style="display:none;">
                    <button class="modal-btn secondary" onclick="closeRescanModal()">Lukk</button>
                    <button class="modal-btn primary" id="openReportBtn" onclick="">Åpne rapport</button>
                </div>
            </div>
        </div>
    </div>
    """ % (base_url, pages, base_url, pages)
    
    injection = modal_html + get_enhancement_js(base_url, total, pages)
    html_content = re.sub(r'</body>', injection + '\n</body>', html_content, flags=re.IGNORECASE)
    
    return html_content


# =============================================================================
# DATA CLASSES AND UTILITIES
# =============================================================================

@dataclass
class MunicipalityResult:
    """Result for a single municipality check."""
    municipality_number: str
    municipality_name: str
    county_number: str
    county_name: str
    url: str
    has_statement: bool = False
    statement_url: Optional[str] = None
    statement_current: bool = False
    statement_last_updated: Optional[str] = None
    wcag_issues: int = 0
    wcag_critical: int = 0
    wcag_serious: int = 0
    report_file: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = ""


def sanitize_filename(name: str) -> str:
    """Sanitize a string to be used as a filename."""
    for old, new in [("/", "-"), ("\\", "-"), (":", "-"), (" ", "_"),
                     ("ae", "ae"), ("oe", "o"), ("aa", "aa"),  
                     ("Ae", "Ae"), ("Oe", "O"), ("Aa", "Aa")]:
        name = name.replace(old, new)
    # Remove any other problematic characters
    return "".join(c for c in name if c.isalnum() or c in "-_.")


def get_all_municipalities(csv_path: str) -> List[dict]:
    """Read CSV and return list of all municipalities."""
    municipalities = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            municipalities.append({
                'county_number': row['County Number'].strip(),
                'county_name': row['County Name'].strip(),
                'municipality_number': row['Municipality Number'].strip(),
                'municipality_name': row['Municipality Name'].strip(),
                'url': row['Official Website'].strip()
            })
    return municipalities


def get_unique_counties(csv_path: str) -> List[dict]:
    """Read CSV and return list of unique counties (one municipality each)."""
    counties = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            county_name = row['County Name'].strip()
            if county_name not in counties:
                counties[county_name] = {
                    'county_number': row['County Number'].strip(),
                    'county_name': county_name,
                    'municipality_number': row['Municipality Number'].strip(),
                    'municipality_name': row['Municipality Name'].strip(),
                    'url': row['Official Website'].strip()
                }
    return list(counties.values())


def run_statement_check(municipality: dict) -> MunicipalityResult:
    """Run only accessibility statement check."""
    from accessibility_statement import AccessibilityStatementChecker
    
    result = MunicipalityResult(
        municipality_number=municipality['municipality_number'],
        municipality_name=municipality['municipality_name'],
        county_number=municipality['county_number'],
        county_name=municipality['county_name'],
        url=municipality['url'],
        timestamp=datetime.now().isoformat()
    )
    
    print(f"  Checking: {municipality['municipality_name']}... ", end='', flush=True)
    
    try:
        checker = AccessibilityStatementChecker(timeout=20)
        stmt_result = checker.check(municipality['url'])
        
        result.has_statement = stmt_result.has_statement_page
        result.statement_url = stmt_result.statement_page_url or stmt_result.uustatus_url
        result.statement_current = stmt_result.is_current
        result.statement_last_updated = stmt_result.last_updated
        
        if result.has_statement and result.statement_current:
            print("OK - Current")
        elif result.has_statement:
            print(f"WARNING - Outdated ({result.statement_last_updated})")
        else:
            print("MISSING")
            
    except Exception as e:
        result.error = str(e)
        print(f"ERROR: {str(e)[:50]}")
    
    return result


def run_full_check(municipality: dict, max_pages: int, output_dir: str) -> MunicipalityResult:
    """Run full WCAG check."""
    from checker import WCAGChecker
    
    result = MunicipalityResult(
        municipality_number=municipality['municipality_number'],
        municipality_name=municipality['municipality_name'],
        county_number=municipality['county_number'],
        county_name=municipality['county_name'],
        url=municipality['url'],
        timestamp=datetime.now().isoformat()
    )
    
    safe_name = sanitize_filename(municipality['municipality_name'])
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(output_dir, f"wcag_{safe_name}_{timestamp}.html")
    
    print(f"\n{'='*60}")
    print(f"Checking: {municipality['municipality_name']} ({municipality['county_name']})")
    print(f"URL: {municipality['url']}")
    print(f"{'='*60}")
    
    try:
        checker = WCAGChecker(
            exclude_patterns=DEFAULT_EXCLUDE_PATTERNS,
            check_statement=True
        )
        
        site_result = checker.crawl_site(municipality['url'], max_pages=max_pages)
        
        # Extract statement info
        if site_result.accessibility_statement:
            stmt = site_result.accessibility_statement
            result.has_statement = stmt.has_statement_page
            result.statement_url = stmt.statement_page_url
            result.statement_current = stmt.is_current
            result.statement_last_updated = stmt.last_updated
        
        # Extract WCAG summary
        summary = site_result.summary
        result.wcag_issues = summary.get('issues', 0)
        result.wcag_critical = summary.get('critical', 0)
        result.wcag_serious = summary.get('serious', 0)
        
        # Generate and save report
        report = checker.generate_report(site_result, format='html')
        
        # Enhance the report with filtering and rescan capabilities
        report = enhance_report(report)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        result.report_file = output_file
        
        print(f"\nResults: {result.wcag_issues} issues ({result.wcag_critical} critical)")
        print(f"Report saved: {output_file} (enhanced)")
        
    except Exception as e:
        result.error = str(e)
        print(f"ERROR: {e}")
    
    return result


def generate_summary(results: List[MunicipalityResult], output_dir: str, mode: str) -> str:
    """Generate summary report."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    total = len(results)
    with_statement = sum(1 for r in results if r.has_statement)
    statement_current = sum(1 for r in results if r.statement_current)
    errors = sum(1 for r in results if r.error)
    
    # Group by county
    by_county = {}
    for r in results:
        if r.county_name not in by_county:
            by_county[r.county_name] = []
        by_county[r.county_name].append(r)
    
    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <title>WCAG Batch Summary - {timestamp}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #003366; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; flex-wrap: wrap; }}
        .stat {{ background: #f5f5f5; padding: 20px; border-radius: 8px; text-align: center; min-width: 150px; }}
        .stat-value {{ font-size: 2em; font-weight: bold; }}
        .ok {{ color: #2e7d32; }}
        .warn {{ color: #e65100; }}
        .error {{ color: #c00; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #003366; color: white; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.85em; }}
        .badge-ok {{ background: #e8f5e9; color: #2e7d32; }}
        .badge-warn {{ background: #fff3e0; color: #e65100; }}
        .badge-error {{ background: #fee; color: #c00; }}
        .county {{ margin: 30px 0; }}
        .county h2 {{ border-bottom: 2px solid #003366; padding-bottom: 10px; }}
    </style>
</head>
<body>
    <h1>WCAG Batch Check Summary</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p>Mode: {mode}</p>
    
    <div class="summary">
        <div class="stat"><div class="stat-value">{total}</div>Total</div>
        <div class="stat"><div class="stat-value ok">{with_statement}</div>Has Statement</div>
        <div class="stat"><div class="stat-value {'ok' if statement_current > total*0.7 else 'warn'}">{statement_current}</div>Current</div>
        <div class="stat"><div class="stat-value warn">{total - with_statement}</div>Missing</div>
        <div class="stat"><div class="stat-value {'error' if errors else ''}">{errors}</div>Errors</div>
    </div>
"""
    
    for county_name in sorted(by_county.keys()):
        municipalities = by_county[county_name]
        html += f"""
    <div class="county">
        <h2>{county_name}</h2>
        <table>
            <tr><th>Kommune</th><th>URL</th><th>Statement</th><th>Status</th><th>Updated</th>"""
        
        if mode == 'full':
            html += "<th>Issues</th><th>Report</th>"
        html += "</tr>"
        
        for m in sorted(municipalities, key=lambda x: x.municipality_name):
            stmt_badge = 'badge-ok' if m.has_statement else 'badge-error'
            stmt_text = 'Yes' if m.has_statement else 'No'
            
            status = ''
            if m.has_statement:
                if m.statement_current:
                    status = '<span class="badge badge-ok">Current</span>'
                else:
                    status = '<span class="badge badge-warn">Outdated</span>'
            
            html += f"""
            <tr>
                <td><strong>{m.municipality_name}</strong></td>
                <td><a href="{m.url}">{m.url}</a></td>
                <td><span class="badge {stmt_badge}">{stmt_text}</span></td>
                <td>{status}</td>
                <td>{m.statement_last_updated or '-'}</td>"""
            
            if mode == 'full':
                issues_class = 'badge-error' if m.wcag_critical > 0 else ('badge-warn' if m.wcag_issues > 0 else 'badge-ok')
                report_link = f'<a href="{os.path.basename(m.report_file)}">View</a>' if m.report_file else '-'
                html += f"""
                <td><span class="badge {issues_class}">{m.wcag_issues}</span></td>
                <td>{report_link}</td>"""
            
            html += "</tr>"
        
        html += "</table></div>"
    
    html += "</body></html>"
    
    # Save files
    html_file = os.path.join(output_dir, f"batch_summary_{timestamp}.html")
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    json_file = os.path.join(output_dir, f"batch_summary_{timestamp}.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': timestamp,
            'mode': mode,
            'total': total,
            'with_statement': with_statement,
            'statement_current': statement_current,
            'errors': errors,
            'results': [asdict(r) for r in results]
        }, f, indent=2, ensure_ascii=False)
    
    return html_file


def update_reports_index(output_base: str):
    """Update the global reports index file."""
    index_file = os.path.join(output_base, "reports_index.json")
    
    # Scan for all report folders
    folders = []
    if os.path.exists(output_base):
        for item in os.listdir(output_base):
            folder_path = os.path.join(output_base, item)
            manifest_path = os.path.join(folder_path, "manifest.json")
            if os.path.isdir(folder_path) and os.path.exists(manifest_path):
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        manifest = json.load(f)
                        folders.append({
                            'folder': item,
                            'timestamp': manifest.get('timestamp', ''),
                            'mode': manifest.get('mode', ''),
                            'description': manifest.get('description', ''),
                            'total': manifest.get('total', 0),
                            'with_statement': manifest.get('with_statement', 0),
                            'total_issues': manifest.get('total_issues', 0),
                            'critical_issues': manifest.get('critical_issues', 0)
                        })
                except:
                    pass
    
    # Sort by timestamp descending
    folders.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Write index
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump({
            'updated': datetime.now().isoformat(),
            'folders': folders
        }, f, indent=2, ensure_ascii=False)
    
    return index_file


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='WCAG Batch Checker (Simple Version)')
    parser.add_argument('--all', action='store_true', help='Check all municipalities')
    parser.add_argument('--counties-only', action='store_true', help='One per county')
    parser.add_argument('--county', type=str, help='Check specific county')
    parser.add_argument('--municipality', type=str, help='Check specific municipality')
    parser.add_argument('--statement-only', action='store_true', help='Only check statement (fast)')
    parser.add_argument('--max-pages', type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument('--output-base', type=str, default=OUTPUT_BASE, help='Base folder for reports')
    parser.add_argument('--csv', type=str, default=CSV_PATH)
    parser.add_argument('--folder-name', type=str, help='Custom folder name (default: timestamp)')
    
    args = parser.parse_args()
    
    # Get municipalities to check
    if args.municipality:
        all_munis = get_all_municipalities(args.csv)
        municipalities = [m for m in all_munis if args.municipality.lower() in m['municipality_name'].lower()]
        desc = f"Municipality: {args.municipality}"
    elif args.county:
        all_munis = get_all_municipalities(args.csv)
        municipalities = [m for m in all_munis if args.county.lower() in m['county_name'].lower()]
        desc = f"County: {args.county}"
    elif args.all:
        municipalities = get_all_municipalities(args.csv)
        desc = "All municipalities"
    else:
        municipalities = get_unique_counties(args.csv)
        desc = "One per county (sample)"
    
    if not municipalities:
        print("No municipalities found!")
        return
    
    mode = 'statement' if args.statement_only else 'full'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create timestamped output folder
    folder_name = args.folder_name if args.folder_name else timestamp
    output_dir = os.path.join(args.output_base, folder_name)
    
    print("=" * 60)
    print("WCAG Batch Checker (Simple Version)")
    print("=" * 60)
    print(f"Mode: {'Statement only' if args.statement_only else 'Full WCAG'}")
    print(f"Scope: {desc}")
    print(f"Municipalities: {len(municipalities)}")
    print(f"Output folder: {output_dir}")
    print("=" * 60)
    
    os.makedirs(output_dir, exist_ok=True)
    
    results = []
    for i, muni in enumerate(municipalities, 1):
        print(f"\n[{i}/{len(municipalities)}]", end='')
        
        if args.statement_only:
            result = run_statement_check(muni)
        else:
            result = run_full_check(muni, args.max_pages, output_dir)
        
        results.append(result)
    
    # Generate summary
    print("\n" + "=" * 60)
    print("Generating summary...")
    summary_file = generate_summary(results, output_dir, mode)
    
    # Calculate totals
    total_issues = sum(r.wcag_issues for r in results)
    critical_issues = sum(r.wcag_critical for r in results)
    
    # Create manifest for this folder
    manifest = {
        'timestamp': timestamp,
        'mode': mode,
        'description': desc,
        'total': len(results),
        'with_statement': sum(1 for r in results if r.has_statement),
        'statement_current': sum(1 for r in results if r.statement_current),
        'errors': sum(1 for r in results if r.error),
        'total_issues': total_issues,
        'critical_issues': critical_issues,
        'summary_file': os.path.basename(summary_file),
        'reports': [
            {
                'municipality': r.municipality_name,
                'county': r.county_name,
                'file': os.path.basename(r.report_file) if r.report_file else None,
                'issues': r.wcag_issues,
                'critical': r.wcag_critical,
                'has_statement': r.has_statement,
                'statement_current': r.statement_current,
                'statement_date': r.statement_last_updated[:10] if r.statement_last_updated else None
            }
            for r in results
        ]
    }
    
    manifest_file = os.path.join(output_dir, 'manifest.json')
    with open(manifest_file, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    # Update global index
    index_file = update_reports_index(args.output_base)
    
    print("=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"Total: {len(results)}")
    print(f"With statement: {sum(1 for r in results if r.has_statement)}")
    print(f"Current: {sum(1 for r in results if r.statement_current)}")
    print(f"Errors: {sum(1 for r in results if r.error)}")
    print(f"\nOutput folder: {output_dir}")
    print(f"Summary: {summary_file}")
    print(f"Index updated: {index_file}")


if __name__ == "__main__":
    main()
