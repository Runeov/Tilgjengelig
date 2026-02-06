"""
Browser-based page fetching using Playwright.
Provides JavaScript rendering support for dynamic websites.
"""

from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse

# Global browser instance for reuse across requests
_browser = None
_playwright = None


def _check_playwright_installed():
    """Check if Playwright is installed and provide helpful error message."""
    try:
        from playwright.sync_api import sync_playwright
        return True
    except ImportError:
        raise ImportError(
            "Playwright is not installed. Install it with:\n"
            "  pip install playwright\n"
            "  playwright install chromium\n\n"
            "Or run without --browser flag to use fast static fetching."
        )


def get_browser():
    """Get or create a browser instance (lazy initialization)."""
    global _browser, _playwright

    if _browser is None:
        _check_playwright_installed()
        from playwright.sync_api import sync_playwright

        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-gpu',
                '--disable-dev-shm-usage',
                '--disable-setuid-sandbox',
                '--no-sandbox',
            ]
        )

    return _browser


def close_browser():
    """Close the browser and cleanup resources."""
    global _browser, _playwright

    if _browser is not None:
        try:
            _browser.close()
        except Exception:
            pass
        _browser = None

    if _playwright is not None:
        try:
            _playwright.stop()
        except Exception:
            pass
        _playwright = None


def fetch_page_with_browser(
    url: str,
    wait_for: str = 'load',
    timeout: int = 30000,
    user_agent: str = None
) -> Optional[Tuple[str, str]]:
    """
    Fetch a page using a headless browser with JavaScript execution.

    Args:
        url: The URL to fetch
        wait_for: Wait strategy - 'networkidle', 'load', 'domcontentloaded',
                  or a CSS selector to wait for
        timeout: Timeout in milliseconds
        user_agent: Optional custom user agent

    Returns:
        Tuple of (html_content, final_url) or None on error
    """
    try:
        browser = get_browser()
        context = browser.new_context(
            user_agent=user_agent or "WCAGChecker/1.0 (Accessibility Compliance Tool; Playwright)"
        )
        page = context.new_page()

        try:
            # Determine wait strategy
            if wait_for in ('networkidle', 'load', 'domcontentloaded'):
                page.goto(url, wait_until=wait_for, timeout=timeout)
            else:
                # Treat as CSS selector
                page.goto(url, wait_until='load', timeout=timeout)
                try:
                    page.wait_for_selector(wait_for, timeout=timeout)
                except Exception:
                    # Selector not found, continue with what we have
                    pass

            # Get the final URL (after any redirects)
            final_url = page.url

            # Get the rendered HTML
            html = page.content()

            return html, final_url

        finally:
            context.close()

    except Exception as e:
        print(f"Browser fetch error for {url}: {e}")
        return None


def extract_links_from_browser(
    url: str,
    wait_for: str = 'load',
    timeout: int = 30000,
    user_agent: str = None
) -> Optional[Tuple[str, str, list]]:
    """
    Fetch a page and extract links from the rendered DOM.

    Args:
        url: The URL to fetch
        wait_for: Wait strategy
        timeout: Timeout in milliseconds
        user_agent: Optional custom user agent

    Returns:
        Tuple of (html_content, final_url, links) or None on error
    """
    try:
        browser = get_browser()
        context = browser.new_context(
            user_agent=user_agent or "WCAGChecker/1.0 (Accessibility Compliance Tool; Playwright)"
        )
        page = context.new_page()

        try:
            # Navigate with appropriate wait strategy
            if wait_for in ('networkidle', 'load', 'domcontentloaded'):
                page.goto(url, wait_until=wait_for, timeout=timeout)
            else:
                page.goto(url, wait_until='load', timeout=timeout)
                try:
                    page.wait_for_selector(wait_for, timeout=timeout)
                except Exception:
                    pass

            final_url = page.url
            html = page.content()

            # Extract links from rendered DOM
            base_domain = urlparse(final_url).netloc
            links = []

            link_elements = page.query_selector_all('a[href]')
            for link in link_elements:
                href = link.get_attribute('href')
                if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                    full_url = urljoin(final_url, href)
                    parsed = urlparse(full_url)

                    # Only include same domain
                    if parsed.netloc == base_domain:
                        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        if parsed.query:
                            clean_url += f"?{parsed.query}"
                        links.append(clean_url)

            return html, final_url, list(set(links))

        finally:
            context.close()

    except Exception as e:
        print(f"Browser fetch error for {url}: {e}")
        return None
