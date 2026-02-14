"""
Fix HTML escaping in existing report files.

The old report template in checker.py didn't escape issue.issue and issue.fix text,
causing raw HTML tags like <title> to break page rendering. This script fixes all
existing HTML report files by escaping the content in <div class="fix"> and issue <p> tags.
"""
import re
import glob
import os
import sys


def escape_html_in_text(text):
    """Escape < and > that are part of content, not part of the report HTML structure."""
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


def fix_file(filepath):
    """Fix HTML escaping in a single report file. Returns True if file was modified."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Fix <div class="fix">...</div> lines
    # The fix text is always on a single line: <div class="fix">CONTENT</div>
    def fix_div_fix(match):
        prefix = match.group(1)  # <div class="fix">
        inner = match.group(2)   # the content
        suffix = match.group(3)  # </div>
        # Check if already escaped (contains &lt; but no raw < in content)
        if '<' not in inner:
            return match.group(0)  # already clean
        escaped = escape_html_in_text(inner)
        return prefix + escaped + suffix

    content = re.sub(
        r'(<div class="fix">)(.*?)(</div>)',
        fix_div_fix,
        content
    )

    # Fix <p>...</p> inside issue divs - these contain issue.issue text
    # Pattern: appears right after the impact span line, inside .issue divs
    # We look for <p> tags that contain unescaped HTML and are preceded by issue context
    def fix_issue_p(match):
        prefix = match.group(1)
        inner = match.group(2)
        suffix = match.group(3)
        if '<' not in inner:
            return match.group(0)
        escaped = escape_html_in_text(inner)
        return prefix + escaped + suffix

    # Match <p> tags that follow impact spans (issue description text)
    # The pattern in the template is:
    #     </div>
    #     <span class="impact ...">...</span>
    # </div>
    # <p>ISSUE TEXT</p>
    content = re.sub(
        r'(</div>\s*<span class="impact[^"]*">[^<]*</span>\s*</div>\s*<p>)(.*?)(</p>)',
        fix_issue_p,
        content,
        flags=re.DOTALL
    )

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    reports_dir = os.path.join(base_dir, 'reports', 'counties')

    # Find all HTML report files in county subdirectories
    pattern = os.path.join(reports_dir, '*', '*.html')
    files = glob.glob(pattern)

    if not files:
        print("No report files found!")
        return

    print(f"Found {len(files)} report files to check...")

    fixed_count = 0
    error_count = 0

    for filepath in sorted(files):
        try:
            if fix_file(filepath):
                fixed_count += 1
                name = os.path.basename(filepath)
                if fixed_count <= 20:  # Only print first 20
                    print(f"  Fixed: {name}")
        except Exception as e:
            error_count += 1
            print(f"  ERROR: {os.path.basename(filepath)}: {e}")

    if fixed_count > 20:
        print(f"  ... and {fixed_count - 20} more")

    print(f"\nDone! Fixed {fixed_count} of {len(files)} files ({error_count} errors)")


if __name__ == '__main__':
    main()
