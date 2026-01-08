#!/usr/bin/env python3
"""
Update the reports index from existing report folders.
Run this after manually adding folders or to refresh the dashboard.
"""

import os
import json
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_BASE = os.path.join(SCRIPT_DIR, "reports")


def update_reports_index(output_base: str = OUTPUT_BASE):
    """Scan report folders and update the global index."""
    index_file = os.path.join(output_base, "reports_index.json")
    
    folders = []
    
    if not os.path.exists(output_base):
        os.makedirs(output_base, exist_ok=True)
        print(f"Created reports folder: {output_base}")
    
    print(f"Scanning: {output_base}")
    
    for item in sorted(os.listdir(output_base), reverse=True):
        folder_path = os.path.join(output_base, item)
        
        if not os.path.isdir(folder_path):
            continue
            
        manifest_path = os.path.join(folder_path, "manifest.json")
        
        if os.path.exists(manifest_path):
            # Has manifest - read it
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                    folders.append({
                        'folder': item,
                        'timestamp': manifest.get('timestamp', item),
                        'mode': manifest.get('mode', ''),
                        'description': manifest.get('description', ''),
                        'total': manifest.get('total', 0),
                        'with_statement': manifest.get('with_statement', 0),
                        'total_issues': manifest.get('total_issues', 0),
                        'critical_issues': manifest.get('critical_issues', 0)
                    })
                    print(f"  ✓ {item}: {manifest.get('total', 0)} reports")
            except Exception as e:
                print(f"  ✗ {item}: Error reading manifest - {e}")
        else:
            # No manifest - try to create one from HTML files
            html_files = [f for f in os.listdir(folder_path) if f.endswith('.html')]
            if html_files:
                print(f"  ? {item}: {len(html_files)} HTML files (no manifest)")
                
                # Create basic manifest
                manifest = {
                    'timestamp': item,
                    'mode': 'unknown',
                    'description': 'Imported folder',
                    'total': len(html_files),
                    'with_statement': 0,
                    'reports': [{'file': f, 'municipality': f.replace('wcag_', '').rsplit('_', 2)[0]} 
                               for f in html_files if f.startswith('wcag_')]
                }
                
                # Save manifest
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2, ensure_ascii=False)
                print(f"    Created manifest.json")
                
                folders.append({
                    'folder': item,
                    'timestamp': item,
                    'mode': 'unknown',
                    'description': 'Imported folder',
                    'total': len(html_files),
                    'with_statement': 0,
                    'total_issues': 0,
                    'critical_issues': 0
                })
            else:
                print(f"  - {item}: Empty or no HTML files")
    
    # Sort by timestamp descending
    folders.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Write index
    index_data = {
        'updated': datetime.now().isoformat(),
        'folders': folders
    }
    
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nIndex updated: {index_file}")
    print(f"Total folders: {len(folders)}")
    
    return index_file


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Update WCAG Reports Index')
    parser.add_argument('--reports-dir', type=str, default=OUTPUT_BASE,
                       help='Path to reports folder')
    
    args = parser.parse_args()
    update_reports_index(args.reports_dir)


if __name__ == "__main__":
    main()
