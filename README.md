# WCAG 2.1 Compliance Checker

A Python-based automated accessibility checker that crawls websites and identifies WCAG 2.1 compliance issues.

## Features

- **Comprehensive WCAG 2.1 Coverage**: Checks 48 WCAG criteria across all four principles (Perceivable, Operable, Understandable, Robust)
- **Multi-page Crawling**: Automatically discovers and checks linked pages within the same domain
- **Multiple Report Formats**: Generate reports in HTML, JSON, or Markdown
- **Detailed Fix Recommendations**: Each issue includes specific guidance on how to fix it
- **Impact Classification**: Issues are categorized by severity (critical, serious, moderate, minor)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Command Line

```bash
# Basic usage - check a single URL
python checker.py https://example.com

# Check multiple pages with custom limit
python checker.py https://example.com --max-pages 20

# Generate different report formats
python checker.py https://example.com --format html
python checker.py https://example.com --format json
python checker.py https://example.com --format markdown
```

### As a Python Module

```python
from checker import WCAGChecker

# Create checker instance
checker = WCAGChecker()

# Check a single page
result = checker.check_page("https://example.com")

# Crawl entire site
site_result = checker.crawl_site("https://example.com", max_pages=50)

# Generate report
html_report = checker.generate_report(site_result, format="html")
```

## Checks Performed

### 1. Images (WCAG 1.1.1)
- Missing alt attributes
- Non-descriptive alt text
- Filename as alt text
- SVG accessibility
- Image map areas

### 2. Headings (WCAG 1.3.1, 2.4.6)
- Missing h1
- Skipped heading levels
- Empty headings
- Generic heading text

### 3. Links (WCAG 2.4.4)
- Generic link text ("click here", "read more")
- Empty links
- URL as link text
- New window indication

### 4. Forms (WCAG 1.3.5, 3.3.1, 3.3.2)
- Missing labels
- Placeholder-only labels
- Missing autocomplete attributes
- Fieldset/legend for radio groups

### 5. Color Contrast (WCAG 1.4.3, 1.4.11)
- Text contrast ratio
- Focus indicator visibility
- Link distinguishability

### 6. Keyboard (WCAG 2.1.1, 2.1.2, 2.4.7)
- Non-keyboard accessible controls
- Focus traps
- Positive tabindex values
- Custom controls without keyboard support

### 7. Language (WCAG 3.1.1, 3.1.2)
- Missing lang attribute
- Invalid language codes
- Language changes in content

### 8. Page Structure (WCAG 2.4.1, 2.4.2, 4.1.1)
- Page title
- Landmark regions
- Duplicate IDs
- HTML validation

### 9. Media (WCAG 1.2.2, 1.4.2)
- Video captions
- Audio controls
- Autoplay detection
- Animation controls

### 10. ARIA (WCAG 4.1.2)
- Invalid roles
- Missing required ARIA attributes
- Redundant ARIA
- Accessible names

## Report Output

### HTML Report
A styled, interactive report with:
- Summary statistics
- Issues grouped by page and criterion
- Expandable issue details
- Fix recommendations

### JSON Report
Structured data for integration with other tools:
```json
{
  "base_url": "https://example.com",
  "summary": {
    "pages_checked": 5,
    "total_issues": 23,
    "critical": 3,
    "serious": 10,
    "moderate": 7,
    "minor": 3
  },
  "pages": [...]
}
```

### Markdown Report
Documentation-friendly format for sharing and tracking.

## Limitations

This is a **static HTML analysis tool**. Some checks require:
- **JavaScript execution**: For dynamically generated content, use with Puppeteer/Playwright
- **Visual inspection**: Color contrast with background images, focus visibility with CSS
- **Manual review**: Quality of alt text, error message helpfulness, audio description quality

For full WCAG compliance, combine automated testing with manual accessibility audits.

## Project Structure

```
wcag_checker/
├── checker.py          # Main checker module
├── requirements.txt    # Python dependencies
├── checkers/           # Individual check modules
│   ├── images.py       # Image accessibility
│   ├── headings.py     # Heading structure
│   ├── links.py        # Link accessibility
│   ├── forms.py        # Form accessibility
│   ├── contrast.py     # Color contrast
│   ├── keyboard.py     # Keyboard accessibility
│   ├── language.py     # Language attributes
│   ├── structure.py    # Page structure
│   ├── media.py        # Media accessibility
│   └── aria.py         # ARIA usage
└── utils/              # Utility functions
    └── helpers.py      # Color parsing, selectors, etc.
```

## Contributing

To add new checks:

1. Create a new module in `checkers/`
2. Implement the checker function with signature:
   ```python
   def check_something(soup, url, html):
       """Returns: (issues, passed, warnings)"""
   ```
3. Add to `checkers/__init__.py`
4. Add to checker list in `checker.py`

## License

MIT License

## References

- [WCAG 2.1 Guidelines](https://www.w3.org/TR/WCAG21/)
- [WCAG 2.1 Quick Reference](https://www.w3.org/WAI/WCAG21/quickref/)
- [Norwegian UU Requirements](https://www.uutilsynet.no/)
