#!/usr/bin/env python3
"""
WCAG Dashboard Server
Serves the dashboard and handles live rescan requests.

Usage:
    python wcag_server.py [--port 8000]
    
Then open http://localhost:8000/wcag_dashboard.html
"""

import os
import sys
import json
import re
import threading
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Import the checker module
try:
    from checker import WCAGChecker
    CHECKER_AVAILABLE = True
except ImportError:
    CHECKER_AVAILABLE = False
    print("Warning: checker.py not found. Rescan functionality will be disabled.")

# Store active scans
active_scans = {}


class WCAGRequestHandler(SimpleHTTPRequestHandler):
    """HTTP request handler with WCAG rescan API."""
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path == '/api/scan/status':
            self.handle_scan_status(parsed.query)
        elif parsed.path == '/api/batch/status':
            self.handle_batch_status(parsed.query)
        elif parsed.path == '/api/reports':
            self.handle_list_reports()
        else:
            # Serve static files
            super().do_GET()
    
    def do_POST(self):
        """Handle POST requests."""
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path == '/api/scan/start':
            self.handle_start_scan()
        elif parsed.path == '/api/batch/start':
            self.handle_start_batch()
        else:
            self.send_error(404, "Not Found")
    
    def handle_start_batch(self):
        """Start a batch WCAG scan."""
        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            params = json.loads(body)
        except json.JSONDecodeError:
            self.send_json_response({'error': 'Invalid JSON'}, 400)
            return
        
        scan_type = params.get('type', 'sample')
        value = params.get('value', '')
        max_pages = int(params.get('max_pages', 20))
        
        # Generate scan ID
        scan_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create output folder
        out_dir = os.path.join(SCRIPT_DIR, 'reports', scan_id)
        os.makedirs(out_dir, exist_ok=True)
        
        # Start batch scan in background thread
        scan_state = {
            'id': scan_id,
            'type': scan_type,
            'value': value,
            'max_pages': max_pages,
            'status': 'starting',
            'progress': 0,
            'message': 'Initialiserer...',
            'completed': 0,
            'total': 0,
            'folder': scan_id,
            'error': None
        }
        active_scans[scan_id] = scan_state
        
        thread = threading.Thread(
            target=run_batch_scan_thread,
            args=(scan_id, scan_type, value, max_pages, out_dir)
        )
        thread.daemon = True
        thread.start()
        
        self.send_json_response({
            'scan_id': scan_id,
            'status': 'started',
            'message': 'Batch-skanning startet'
        })
    
    def handle_start_scan(self):
        """Start a new WCAG scan."""
        if not CHECKER_AVAILABLE:
            self.send_json_response({'error': 'Checker not available'}, 503)
            return
        
        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            params = json.loads(body)
        except json.JSONDecodeError:
            self.send_json_response({'error': 'Invalid JSON'}, 400)
            return
        
        url = params.get('url', '').strip()
        max_pages = int(params.get('max_pages', 20))
        output_folder = params.get('output_folder', '')
        
        if not url:
            self.send_json_response({'error': 'URL required'}, 400)
            return
        
        # Generate scan ID
        scan_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Start scan in background thread
        scan_state = {
            'id': scan_id,
            'url': url,
            'max_pages': max_pages,
            'status': 'starting',
            'progress': 0,
            'message': 'Initialiserer...',
            'result': None,
            'error': None,
            'output_file': None
        }
        active_scans[scan_id] = scan_state
        
        # Determine output folder
        if output_folder:
            out_dir = os.path.join(SCRIPT_DIR, 'reports', output_folder)
        else:
            out_dir = os.path.join(SCRIPT_DIR, 'reports', scan_id)
        
        thread = threading.Thread(
            target=run_scan_thread,
            args=(scan_id, url, max_pages, out_dir)
        )
        thread.daemon = True
        thread.start()
        
        self.send_json_response({
            'scan_id': scan_id,
            'status': 'started',
            'message': 'Skanning startet'
        })
    
    def handle_scan_status(self, query):
        """Get status of a scan."""
        params = urllib.parse.parse_qs(query)
        scan_id = params.get('id', [''])[0]
        
        if not scan_id or scan_id not in active_scans:
            self.send_json_response({'error': 'Scan not found'}, 404)
            return
        
        scan = active_scans[scan_id]
        self.send_json_response({
            'id': scan['id'],
            'status': scan['status'],
            'progress': scan['progress'],
            'message': scan['message'],
            'output_file': scan.get('output_file'),
            'error': scan.get('error')
        })
    
    def handle_batch_status(self, query):
        """Get status of a batch scan."""
        params = urllib.parse.parse_qs(query)
        scan_id = params.get('id', [''])[0]
        
        if not scan_id or scan_id not in active_scans:
            self.send_json_response({'error': 'Scan not found'}, 404)
            return
        
        scan = active_scans[scan_id]
        self.send_json_response({
            'id': scan['id'],
            'status': scan['status'],
            'progress': scan['progress'],
            'message': scan['message'],
            'completed': scan.get('completed', 0),
            'total': scan.get('total', 0),
            'folder': scan.get('folder'),
            'error': scan.get('error')
        })
    
    def handle_list_reports(self):
        """List available report folders."""
        reports_dir = os.path.join(SCRIPT_DIR, 'reports')
        folders = []
        
        if os.path.exists(reports_dir):
            for item in sorted(os.listdir(reports_dir), reverse=True):
                folder_path = os.path.join(reports_dir, item)
                manifest_path = os.path.join(folder_path, 'manifest.json')
                
                if os.path.isdir(folder_path) and os.path.exists(manifest_path):
                    try:
                        with open(manifest_path, 'r', encoding='utf-8') as f:
                            manifest = json.load(f)
                            folders.append({
                                'folder': item,
                                'timestamp': manifest.get('timestamp', ''),
                                'description': manifest.get('description', ''),
                                'total': manifest.get('total', 0)
                            })
                    except:
                        pass
        
        self.send_json_response({'folders': folders})
    
    def send_json_response(self, data, status=200):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        """Custom logging."""
        if '/api/' in args[0]:
            print(f"[API] {args[0]}")
        elif not any(x in args[0] for x in ['.js', '.css', '.ico', '.png', '.jpg']):
            print(f"[{self.address_string()}] {args[0]}")


def run_scan_thread(scan_id, url, max_pages, output_dir):
    """Run WCAG scan in background thread."""
    scan = active_scans[scan_id]
    
    try:
        scan['status'] = 'running'
        scan['message'] = f'Kobler til {url}...'
        scan['progress'] = 5
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize checker
        checker = WCAGChecker(
            max_pages=max_pages,
            exclude_patterns=['/aktuelt/', '/nyheter/', '/artikkel/', '/innhold/',
                            '/kunngjoring/', '/arrangement/', '/hendelse/', '/dokument/', '/fil/']
        )
        
        scan['message'] = 'Crawler sider...'
        scan['progress'] = 10
        
        # Run the check
        result = checker.check_site(url, progress_callback=lambda p, m: update_progress(scan_id, p, m))
        
        scan['progress'] = 90
        scan['message'] = 'Genererer rapport...'
        
        # Generate report
        report_html = checker.generate_report(result, format='html')
        
        # Enhance the report with interactive features
        report_html = enhance_report_for_server(report_html)
        
        # Extract municipality name from URL
        domain = url.replace('https://', '').replace('http://', '').replace('www.', '')
        muni_name = domain.split('.')[0].replace('-', '_').title()
        
        # Save report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'wcag_{muni_name}_{timestamp}.html'
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_html)
        
        # Update manifest
        update_folder_manifest(output_dir, result, muni_name, filename)
        
        # Update global index
        update_global_index()
        
        scan['status'] = 'complete'
        scan['progress'] = 100
        scan['message'] = 'Ferdig!'
        scan['output_file'] = os.path.relpath(filepath, SCRIPT_DIR)
        scan['result'] = {
            'total_issues': result.get('summary', {}).get('total', 0),
            'critical': result.get('summary', {}).get('critical', 0),
            'pages_tested': result.get('summary', {}).get('pages_tested', 0)
        }
        
    except Exception as e:
        scan['status'] = 'error'
        scan['error'] = str(e)
        scan['message'] = f'Feil: {str(e)}'
        print(f"Scan error: {e}")


def update_progress(scan_id, progress, message):
    """Update scan progress."""
    if scan_id in active_scans:
        # Map progress 0-100 to 10-90 range
        mapped_progress = 10 + int(progress * 0.8)
        active_scans[scan_id]['progress'] = mapped_progress
        active_scans[scan_id]['message'] = message


def run_batch_scan_thread(scan_id, scan_type, value, max_pages, output_dir):
    """Run batch WCAG scan in background thread."""
    scan = active_scans[scan_id]
    
    try:
        scan['status'] = 'running'
        scan['message'] = 'Laster kommuneliste...'
        scan['progress'] = 5
        
        # Load municipalities from CSV
        csv_path = os.path.join(SCRIPT_DIR, 'counties.csv')
        municipalities = []
        
        if os.path.exists(csv_path):
            import csv
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                all_munis = list(reader)
                
                if scan_type == 'municipality':
                    municipalities = [m for m in all_munis 
                                     if value.lower() in m.get('municipality_name', '').lower()]
                elif scan_type == 'county':
                    municipalities = [m for m in all_munis 
                                     if value.lower() in m.get('county_name', '').lower()]
                elif scan_type == 'sample':
                    # One per county
                    seen_counties = set()
                    for m in all_munis:
                        county = m.get('county_name', '')
                        if county not in seen_counties:
                            municipalities.append(m)
                            seen_counties.add(county)
                elif scan_type == 'all':
                    municipalities = all_munis
        
        if not municipalities:
            scan['status'] = 'error'
            scan['error'] = 'Ingen kommuner funnet'
            scan['message'] = 'Ingen kommuner funnet'
            return
        
        scan['total'] = len(municipalities)
        scan['message'] = f'Starter skanning av {len(municipalities)} kommuner...'
        
        results = []
        
        for i, muni in enumerate(municipalities):
            muni_name = muni.get('municipality_name', 'Unknown')
            url = muni.get('url', '')
            
            if not url:
                continue
            
            progress = int(5 + (i / len(municipalities)) * 90)
            scan['progress'] = progress
            scan['completed'] = i
            scan['message'] = f'Skanner {muni_name} ({i+1}/{len(municipalities)})...'
            
            try:
                # Initialize checker
                checker = WCAGChecker(
                    max_pages=max_pages,
                    exclude_patterns=['/aktuelt/', '/nyheter/', '/artikkel/', '/innhold/',
                                    '/kunngjoring/', '/arrangement/', '/hendelse/', '/dokument/', '/fil/']
                )
                
                # Run check
                result = checker.check_site(url)
                
                # Generate report
                report_html = checker.generate_report(result, format='html')
                
                # Save report
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_name = muni_name.replace(' ', '_').replace('/', '_')
                filename = f'wcag_{safe_name}_{timestamp}.html'
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(report_html)
                
                summary = result.get('summary', {})
                stmt = result.get('accessibility_statement', {})
                stmt_date = stmt.get('last_updated', '')
                results.append({
                    'municipality': muni_name,
                    'county': muni.get('county_name', ''),
                    'file': filename,
                    'issues': summary.get('total', 0),
                    'critical': summary.get('critical', 0),
                    'has_statement': stmt.get('found', False),
                    'statement_current': stmt.get('is_current', False),
                    'statement_date': stmt_date[:10] if stmt_date else None
                })
                
                print(f"  ✓ {muni_name}: {summary.get('total', 0)} issues")
                
            except Exception as e:
                print(f"  ✗ {muni_name}: {e}")
                results.append({
                    'municipality': muni_name,
                    'county': muni.get('county_name', ''),
                    'file': None,
                    'issues': 0,
                    'critical': 0,
                    'has_statement': False,
                    'statement_current': False,
                    'statement_date': None,
                    'error': str(e)
                })
        
        # Create manifest
        manifest = {
            'timestamp': scan_id,
            'mode': 'batch',
            'description': f'{scan_type}: {value}' if value else scan_type,
            'total': len(results),
            'with_statement': sum(1 for r in results if r.get('has_statement')),
            'total_issues': sum(r.get('issues', 0) for r in results),
            'critical_issues': sum(r.get('critical', 0) for r in results),
            'reports': results
        }
        
        manifest_path = os.path.join(output_dir, 'manifest.json')
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        # Update global index
        update_global_index()
        
        scan['status'] = 'complete'
        scan['progress'] = 100
        scan['completed'] = len(results)
        scan['message'] = f'Ferdig! {len(results)} kommuner skannet.'
        
    except Exception as e:
        scan['status'] = 'error'
        scan['error'] = str(e)
        scan['message'] = f'Feil: {str(e)}'
        print(f"Batch scan error: {e}")


def enhance_report_for_server(html_content):
    """Add server-based rescan functionality to report."""
    
    # Find the rescan modal and update it for live scanning
    rescan_modal_js = """
        function showRescanModal() {
            var modal = document.getElementById('rescanModal');
            var inputEl = document.getElementById('maxPages');
            if (modal) modal.classList.add('active');
            if (inputEl) inputEl.value = maxPages;
            document.getElementById('scanStatus').style.display = 'none';
            document.getElementById('scanForm').style.display = 'block';
        }
        
        function closeRescanModal() {
            var modal = document.getElementById('rescanModal');
            if (modal) modal.classList.remove('active');
        }
        
        function startRescan() {
            var inputEl = document.getElementById('maxPages');
            var pages = parseInt(inputEl.value) || 20;
            
            document.getElementById('scanForm').style.display = 'none';
            document.getElementById('scanStatus').style.display = 'block';
            document.getElementById('scanProgress').style.width = '0%';
            document.getElementById('scanMessage').textContent = 'Starter skanning...';
            
            fetch('/api/scan/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: BASE_URL,
                    max_pages: pages
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.scan_id) {
                    pollScanStatus(data.scan_id);
                } else {
                    document.getElementById('scanMessage').textContent = 'Feil: ' + (data.error || 'Ukjent feil');
                }
            })
            .catch(err => {
                document.getElementById('scanMessage').textContent = 'Feil: ' + err.message;
            });
        }
        
        function pollScanStatus(scanId) {
            fetch('/api/scan/status?id=' + scanId)
            .then(r => r.json())
            .then(data => {
                document.getElementById('scanProgress').style.width = data.progress + '%';
                document.getElementById('scanMessage').textContent = data.message;
                
                if (data.status === 'complete') {
                    document.getElementById('scanMessage').innerHTML = 
                        'Ferdig! <a href="/' + data.output_file + '" style="color: #4ade80;">Åpne ny rapport</a>';
                    setTimeout(() => {
                        if (confirm('Skanning ferdig! Vil du åpne den nye rapporten?')) {
                            window.location.href = '/' + data.output_file;
                        }
                    }, 500);
                } else if (data.status === 'error') {
                    document.getElementById('scanMessage').textContent = 'Feil: ' + data.error;
                } else {
                    setTimeout(() => pollScanStatus(scanId), 1000);
                }
            })
            .catch(err => {
                document.getElementById('scanMessage').textContent = 'Feil: ' + err.message;
            });
        }
    """
    
    # Replace the old copyCommand/rescan functions
    html_content = re.sub(
        r'function showRescanModal\(\).*?function copyCommand\(\).*?}\s*\n',
        rescan_modal_js + '\n',
        html_content,
        flags=re.DOTALL
    )
    
    # Update the modal HTML to include progress bar
    old_modal = re.search(r'<div class="modal-overlay" id="rescanModal">.*?</div>\s*</div>\s*</div>', html_content, re.DOTALL)
    if old_modal:
        new_modal = """<div class="modal-overlay" id="rescanModal">
        <div class="modal">
            <h3>🔄 Skann på nytt</h3>
            
            <div id="scanForm">
                <div class="modal-url">{url}</div>
                
                <div class="modal-pages">
                    <label>Maks sider:</label>
                    <input type="number" id="maxPages" value="{pages}" min="1" max="500">
                    <span class="modal-pages-hint">Flere sider = grundigere, men tregere</span>
                </div>
                
                <div class="modal-actions">
                    <button class="modal-btn secondary" onclick="closeRescanModal()">Avbryt</button>
                    <button class="modal-btn primary" onclick="startRescan()">▶ Start skanning</button>
                </div>
            </div>
            
            <div id="scanStatus" style="display: none;">
                <div style="background: #f0f0f0; border-radius: 8px; height: 24px; margin: 20px 0; overflow: hidden;">
                    <div id="scanProgress" style="background: linear-gradient(90deg, #003366, #004488); height: 100%; width: 0%; transition: width 0.3s;"></div>
                </div>
                <p id="scanMessage" style="text-align: center; color: #666;">Starter...</p>
            </div>
        </div>
    </div>""".format(
            url=re.search(r'BASE_URL = "([^"]+)"', html_content).group(1) if re.search(r'BASE_URL = "([^"]+)"', html_content) else '',
            pages=re.search(r'maxPages = (\d+)', html_content).group(1) if re.search(r'maxPages = (\d+)', html_content) else '20'
        )
        html_content = html_content[:old_modal.start()] + new_modal + html_content[old_modal.end():]
    
    return html_content


def update_folder_manifest(folder_path, result, muni_name, filename):
    """Update or create manifest for a report folder."""
    manifest_path = os.path.join(folder_path, 'manifest.json')
    
    # Load existing manifest or create new
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
    else:
        manifest = {
            'timestamp': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'mode': 'full',
            'description': 'Live scan',
            'total': 0,
            'with_statement': 0,
            'total_issues': 0,
            'critical_issues': 0,
            'reports': []
        }
    
    # Add/update report entry
    summary = result.get('summary', {})
    stmt = result.get('accessibility_statement', {})
    stmt_date = stmt.get('last_updated', '')
    new_report = {
        'municipality': muni_name,
        'county': '',
        'file': filename,
        'issues': summary.get('total', 0),
        'critical': summary.get('critical', 0),
        'has_statement': stmt.get('found', False),
        'statement_current': stmt.get('is_current', False),
        'statement_date': stmt_date[:10] if stmt_date else None
    }
    
    # Update or append
    found = False
    for i, r in enumerate(manifest.get('reports', [])):
        if r.get('municipality') == muni_name:
            manifest['reports'][i] = new_report
            found = True
            break
    
    if not found:
        manifest['reports'].append(new_report)
    
    # Update totals
    manifest['total'] = len(manifest['reports'])
    manifest['total_issues'] = sum(r.get('issues', 0) for r in manifest['reports'])
    manifest['critical_issues'] = sum(r.get('critical', 0) for r in manifest['reports'])
    manifest['with_statement'] = sum(1 for r in manifest['reports'] if r.get('has_statement'))
    
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def update_global_index():
    """Update the global reports index."""
    reports_dir = os.path.join(SCRIPT_DIR, 'reports')
    index_file = os.path.join(reports_dir, 'reports_index.json')
    
    folders = []
    
    if os.path.exists(reports_dir):
        for item in sorted(os.listdir(reports_dir), reverse=True):
            folder_path = os.path.join(reports_dir, item)
            manifest_path = os.path.join(folder_path, 'manifest.json')
            
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
    
    folders.sort(key=lambda x: x['timestamp'], reverse=True)
    
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump({
            'updated': datetime.now().isoformat(),
            'folders': folders
        }, f, indent=2, ensure_ascii=False)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='WCAG Dashboard Server')
    parser.add_argument('--port', type=int, default=8000, help='Port to run on (default: 8000)')
    parser.add_argument('--host', type=str, default='localhost', help='Host to bind to (default: localhost)')
    
    args = parser.parse_args()
    
    # Change to script directory
    os.chdir(SCRIPT_DIR)
    
    # Create reports folder if needed
    os.makedirs('reports', exist_ok=True)
    
    # Create initial index if needed
    index_file = os.path.join('reports', 'reports_index.json')
    if not os.path.exists(index_file):
        with open(index_file, 'w') as f:
            json.dump({'updated': datetime.now().isoformat(), 'folders': []}, f)
    
    print("=" * 60)
    print("WCAG Dashboard Server")
    print("=" * 60)
    print(f"Server running at: http://{args.host}:{args.port}")
    print(f"Dashboard: http://{args.host}:{args.port}/wcag_dashboard.html")
    print(f"Checker available: {'Yes' if CHECKER_AVAILABLE else 'No (install checker.py)'}")
    print("=" * 60)
    print("Press Ctrl+C to stop\n")
    
    server = HTTPServer((args.host, args.port), WCAGRequestHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
