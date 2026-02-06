# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WCAG 2.1 Compliance Checker - A Python-based automated accessibility testing tool that crawls websites and identifies WCAG 2.1 compliance issues. Based on official Norwegian UU-tilsynet (Universal Design Authority) test rules.

## Commands

### Single URL Check
```bash
python checker.py https://example.com --max-pages 20 --format html
python checker.py https://example.com --format json --exclude "/old/,/archive/"
python checker.py https://example.com --no-dedupe  # Don't deduplicate article errors
```

### JavaScript-Heavy Sites (Browser Mode)
```bash
# Use headless browser for SPAs and JS-rendered content
python checker.py https://spa-site.com --browser --max-pages 20

# Wait for specific element to appear
python checker.py https://spa-site.com --browser --wait-for "#main-content"

# Wait for network to be idle (slower but more thorough)
python checker.py https://spa-site.com --browser --wait-for networkidle
```

### Alternative CLI Entry Point
```bash
python run.py https://example.com --max-pages 20
python run.py https://example.com --single-page  # Check only the specified URL
python run.py https://example.com --quiet        # Suppress progress output
python run.py https://spa-site.com --browser     # Enable browser mode
```

### Batch Check (Norwegian Municipalities)
```bash
python batch_check.py --all                    # Check all municipalities
python batch_check.py --all --statement-only   # Quick accessibility statement check only
python batch_check.py --counties-only          # One municipality per county
python batch_check.py --county "Oslo"          # Specific county
python batch_check.py --municipality "Bergen"  # Specific municipality
```

### Running Tests
```bash
python test_checker.py  # Requires test_page.html in working directory
```

### Install Dependencies
```bash
pip install -r requirements.txt  # beautifulsoup4, requests, lxml

# For browser mode (optional - enables --browser flag):
pip install playwright
playwright install chromium
```

## Architecture

### Core Components

**checker.py** - Main orchestrator containing:
- `WCAGChecker` class: Site crawling, page checking, report generation
- `Issue`, `PageResult`, `SiteResult` dataclasses for structured results
- Article page deduplication to reduce noise from similar news/blog pages
- Accessibility statement detection (checks uustatus.no API)
- Optional browser-based fetching via `use_browser` parameter

**browser_fetch.py** - Browser-based page fetching module:
- Playwright integration for JavaScript rendering
- Lazy browser initialization (only starts when needed)
- Configurable wait strategies: `load`, `networkidle`, `domcontentloaded`, or CSS selector
- Link extraction from rendered DOM for multi-page crawling

**checkers/** - Individual WCAG criterion checkers, each with signature:
```python
def check_something(soup: BeautifulSoup, url: str, html: str) -> tuple[list[Issue], list[str], list[Warning]]:
    """Returns (issues, passed_checks, warnings)"""
```

Available checkers: `images`, `headings`, `links`, `forms`, `contrast`, `keyboard`, `language`, `structure`, `media`, `aria`, `use_of_color`, `name_role_value`, `non_text_contrast`

**uu_test_rules.py** - Complete mapping of Norwegian UU-tilsynet test rules to WCAG criteria. Each rule has Norwegian/English names, WCAG criterion ID, level (A/AA/AAA), and automation capability.

**utils/helpers.py** - Shared utilities:
- Color parsing (hex, rgb, rgba, hsl, named colors)
- WCAG contrast ratio calculation
- CSS selector generation
- Accessible name extraction

### Adding New Checkers

1. Create `checkers/new_checker.py` with the standard function signature
2. Add import and export in `checkers/__init__.py`
3. Add to the `checkers` list in `WCAGChecker.__init__` in `checker.py`

### Issue Structure

Issues use the `Issue` dataclass with fields: `rule_id` (UU test rule), `criterion_id` (WCAG), `criterion_name`, `criterion_name_en`, `level`, `impact` (critical/serious/moderate/minor), `element`, `selector`, `issue`, `fix`, `context`

## Key Behaviors

- Default: Static HTML analysis using `requests` (fast, no JavaScript)
- Browser mode (`--browser`): Full JavaScript rendering via Playwright headless browser
- Skips file downloads (PDF, images, etc.) during crawl
- Deduplicates recurring issues in article/news pages
- Checks for accessibility statements on uustatus.no
- Reports support Norwegian language output
- Exit code 1 if critical issues found, 0 otherwise

## Browser Mode

Use `--browser` flag for JavaScript-heavy sites (SPAs, React apps, etc.):

| Wait Strategy | Description |
|--------------|-------------|
| `load` (default) | Wait for page load event |
| `domcontentloaded` | Wait for DOM content loaded |
| `networkidle` | Wait for network to be idle (slower) |
| CSS selector | Wait for specific element, e.g., `#main-content` |

Browser mode extracts links from the rendered DOM, enabling multi-page crawling of JS-rendered navigation.
