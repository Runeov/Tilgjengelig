#!/usr/bin/env python3
"""Test the WCAG checker on a local HTML file."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bs4 import BeautifulSoup
from checkers.images import check_images
from checkers.headings import check_headings
from checkers.links import check_links
from checkers.forms import check_forms
from checkers.contrast import check_contrast
from checkers.keyboard import check_keyboard
from checkers.language import check_language
from checkers.structure import check_structure
from checkers.media import check_media
from checkers.aria import check_aria


def test_checker():
    """Run all checkers on test HTML."""
    # Read test file
    with open('test_page.html', 'r') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    url = "file://test_page.html"
    
    checkers = [
        ("Images", check_images),
        ("Headings", check_headings),
        ("Links", check_links),
        ("Forms", check_forms),
        ("Contrast", check_contrast),
        ("Keyboard", check_keyboard),
        ("Language", check_language),
        ("Structure", check_structure),
        ("Media", check_media),
        ("ARIA", check_aria),
    ]
    
    total_issues = 0
    total_passed = 0
    total_warnings = 0
    
    print("=" * 60)
    print("WCAG 2.1 Compliance Check Results")
    print("=" * 60)
    
    for name, checker_func in checkers:
        try:
            issues, passed, warnings = checker_func(soup, url, html)
            
            print(f"\n## {name}")
            print(f"   Issues: {len(issues)} | Passed: {len(passed)} | Warnings: {len(warnings)}")
            
            for issue in issues:
                print(f"   ❌ [{issue.criterion_id}] {issue.issue}")
                print(f"      Fix: {issue.fix}")
            
            for warning in warnings[:3]:  # Limit warnings displayed
                print(f"   ⚠️  [{warning.criterion_id}] {warning.issue}")
            
            total_issues += len(issues)
            total_passed += len(passed)
            total_warnings += len(warnings)
            
        except Exception as e:
            print(f"\n## {name}")
            print(f"   ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total Issues:   {total_issues}")
    print(f"Total Passed:   {total_passed}")
    print(f"Total Warnings: {total_warnings}")
    print("=" * 60)
    
    return total_issues, total_passed, total_warnings


if __name__ == "__main__":
    test_checker()
