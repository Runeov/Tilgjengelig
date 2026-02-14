#!/usr/bin/env python3
"""
Script to analyze websites for mobile apps and accessibility declarations.
Reads from FinnmarkPublic.csv and outputs results to a new CSV file.
"""

import csv
import re
import time
import urllib.parse
from typing import Optional, Tuple, List
import requests
from bs4 import BeautifulSoup

# Constants
INPUT_CSV = r"Virksomheter\FinnmarkPublic.csv"
OUTPUT_CSV = r"Virksomheter\FinnmarkPublic_apps_accessibility.csv"
REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 2
DELAY_BETWEEN_REQUESTS = 1  # seconds

# Patterns for app store detection
APP_STORE_PATTERNS = [
    r'apps\.apple\.com',
    r'itunes\.apple\.com',
    r'appstore',
    r'app\s+store',
]

GOOGLE_PLAY_PATTERNS = [
    r'play\.google\.com',
    r'google\s+play',
    r'play\s+store',
]

APP_TEXT_PATTERNS = [
    r'last\s+ned\s+app',
    r'download\s+app',
    r'vår\s+app',
    r'our\s+app',
    r'mobilapp',
    r'mobil\s+app',
    r'last\s+ned',
]

# Patterns for accessibility declaration detection
ACCESSIBILITY_PATTERNS = [
    r'tilgjengelighetserklæring',
    r'tilgjengelighet',
    r'uu-status',
    r'universell\s+utforming',
    r'accessibility\s+statement',
    r'tilgjengelighetsstatus',
]

ACCESSIBILITY_URL_PATTERNS = [
    r'/tilgjengelighet',
    r'/uu',
    r'/accessibility',
    r'/uu-status',
    r'tilgjengelighetserklæring',
]


def normalize_url(url: str) -> str:
    """Normalize URL to ensure it has a scheme."""
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url


def fetch_website(url: str) -> Tuple[Optional[requests.Response], Optional[str]]:
    """
    Fetch a website with retries and error handling.
    Returns (response, error_message).
    """
    url = normalize_url(url)
    if not url:
        return None, "Empty URL"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'nb-NO,nb,no;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True
            )
            response.raise_for_status()
            return response, None
        except requests.exceptions.Timeout:
            if attempt == MAX_RETRIES - 1:
                return None, "Timeout"
            time.sleep(2)
        except requests.exceptions.ConnectionError:
            if attempt == MAX_RETRIES - 1:
                return None, "Connection Error"
            time.sleep(2)
        except requests.exceptions.HTTPError as e:
            return None, f"HTTP Error: {e.response.status_code}"
        except requests.exceptions.RequestException as e:
            return None, f"Request Error: {str(e)}"
    
    return None, "Unknown Error"


def extract_app_store_links(soup: BeautifulSoup, base_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract iOS and Android app store links from the page.
    Returns (ios_link, android_link).
    """
    ios_link = None
    android_link = None
    
    # Parse base URL for constructing absolute URLs
    parsed_base = urllib.parse.urlparse(base_url)
    base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
    
    # Find all links
    for link in soup.find_all('a', href=True):
        href = link['href'].lower()
        text = link.get_text(strip=True).lower()
        
        # Check for iOS App Store
        if not ios_link:
            for pattern in APP_STORE_PATTERNS:
                if re.search(pattern, href, re.IGNORECASE):
                    ios_link = link['href']
                    if not ios_link.startswith('http'):
                        ios_link = urllib.parse.urljoin(base_domain, ios_link)
                    break
        
        # Check for Google Play
        if not android_link:
            for pattern in GOOGLE_PLAY_PATTERNS:
                if re.search(pattern, href, re.IGNORECASE):
                    android_link = link['href']
                    if not android_link.startswith('http'):
                        android_link = urllib.parse.urljoin(base_domain, android_link)
                    break
    
    return ios_link, android_link


def extract_accessibility_info(soup: BeautifulSoup, base_url: str) -> Tuple[bool, Optional[str]]:
    """
    Extract accessibility declaration information from the page.
    Returns (has_declaration, declaration_url).
    """
    has_declaration = False
    declaration_url = None
    
    # Parse base URL for constructing absolute URLs
    parsed_base = urllib.parse.urlparse(base_url)
    base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
    
    # Find all links
    for link in soup.find_all('a', href=True):
        href = link['href'].lower()
        text = link.get_text(strip=True).lower()
        
        # Check URL patterns
        for pattern in ACCESSIBILITY_URL_PATTERNS:
            if re.search(pattern, href, re.IGNORECASE):
                has_declaration = True
                declaration_url = link['href']
                if not declaration_url.startswith('http'):
                    declaration_url = urllib.parse.urljoin(base_domain, declaration_url)
                return has_declaration, declaration_url
        
        # Check text patterns
        for pattern in ACCESSIBILITY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                has_declaration = True
                declaration_url = link['href']
                if not declaration_url.startswith('http'):
                    declaration_url = urllib.parse.urljoin(base_domain, declaration_url)
                return has_declaration, declaration_url
    
    # Also check the page text for accessibility mentions
    page_text = soup.get_text(separator=' ', strip=True).lower()
    for pattern in ACCESSIBILITY_PATTERNS:
        if re.search(pattern, page_text, re.IGNORECASE):
            has_declaration = True
            break
    
    return has_declaration, declaration_url


def analyze_website(website_url: str) -> dict:
    """
    Analyze a website for apps and accessibility declarations.
    Returns a dictionary with the analysis results.
    """
    result = {
        'har_app_ios': 'No',
        'har_app_android': 'No',
        'app_link_ios': '',
        'app_link_android': '',
        'har_tilgjengelighetserklæring': 'No',
        'tilgjengelighet_url': '',
        'notes': ''
    }
    
    # Fetch the website
    response, error = fetch_website(website_url)
    
    if error:
        result['har_app_ios'] = 'Error'
        result['har_app_android'] = 'Error'
        result['har_tilgjengelighetserklæring'] = 'Error'
        result['notes'] = error
        return result
    
    # Parse HTML
    soup = BeautifulSoup(response.content, 'html.parser')
    final_url = response.url  # Use the final URL after redirects
    
    # Extract app store links
    ios_link, android_link = extract_app_store_links(soup, final_url)
    
    if ios_link:
        result['har_app_ios'] = 'Yes'
        result['app_link_ios'] = ios_link
    
    if android_link:
        result['har_app_android'] = 'Yes'
        result['app_link_android'] = android_link
    
    # Extract accessibility info
    has_accessibility, accessibility_url = extract_accessibility_info(soup, final_url)
    
    if has_accessibility:
        result['har_tilgjengelighetserklæring'] = 'Yes'
        if accessibility_url:
            result['tilgjengelighet_url'] = accessibility_url
    
    # Add notes if we found something interesting
    notes_parts = []
    if ios_link or android_link:
        notes_parts.append("App found")
    if has_accessibility:
        notes_parts.append("Accessibility declaration found")
    
    if notes_parts:
        result['notes'] = "; ".join(notes_parts)
    
    return result


def read_input_csv(filepath: str) -> List[dict]:
    """Read the input CSV and return list of rows."""
    rows = []
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception as e:
        print(f"Error reading CSV: {e}")
    return rows


def write_output_csv(filepath: str, data: List[dict]):
    """Write results to output CSV."""
    fieldnames = [
        'Virksomhet',
        'Nettside',
        'Har_app_iOS',
        'Har_app_Android',
        'App_link_iOS',
        'App_link_Android',
        'Har_tilgjengelighetserklæring',
        'Tilgjengelighet_URL',
        'Notes'
    ]
    
    try:
        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        print(f"Results written to: {filepath}")
    except Exception as e:
        print(f"Error writing CSV: {e}")


def main():
    """Main function to run the analysis."""
    print("Starting website analysis...")
    print(f"Reading from: {INPUT_CSV}")
    
    # Read input CSV
    input_rows = read_input_csv(INPUT_CSV)
    print(f"Found {len(input_rows)} rows to process")
    
    results = []
    
    for i, row in enumerate(input_rows, 1):
        # Extract company name and website
        company = row.get('Virksomhet', '').strip()
        website = row.get('Offisiell nettside', '').strip()
        
        if not company or not website:
            print(f"[{i}/{len(input_rows)}] Skipping row - missing company or website")
            continue
        
        print(f"[{i}/{len(input_rows)}] Analyzing: {company} ({website})")
        
        # Analyze the website
        analysis = analyze_website(website)
        
        # Build result row
        result = {
            'Virksomhet': company,
            'Nettside': website,
            'Har_app_iOS': analysis['har_app_ios'],
            'Har_app_Android': analysis['har_app_android'],
            'App_link_iOS': analysis['app_link_ios'],
            'App_link_Android': analysis['app_link_android'],
            'Har_tilgjengelighetserklæring': analysis['har_tilgjengelighetserklæring'],
            'Tilgjengelighet_URL': analysis['tilgjengelighet_url'],
            'Notes': analysis['notes']
        }
        
        results.append(result)
        
        # Add delay between requests
        if i < len(input_rows):
            time.sleep(DELAY_BETWEEN_REQUESTS)
    
    # Write output CSV
    print(f"\nWriting results to: {OUTPUT_CSV}")
    write_output_csv(OUTPUT_CSV, results)
    
    # Print summary
    print("\n--- Summary ---")
    total = len(results)
    ios_apps = sum(1 for r in results if r['Har_app_iOS'] == 'Yes')
    android_apps = sum(1 for r in results if r['Har_app_Android'] == 'Yes')
    accessibility = sum(1 for r in results if r['Har_tilgjengelighetserklæring'] == 'Yes')
    errors = sum(1 for r in results if r['Har_app_iOS'] == 'Error')
    
    print(f"Total websites analyzed: {total}")
    print(f"Websites with iOS app: {ios_apps}")
    print(f"Websites with Android app: {android_apps}")
    print(f"Websites with accessibility declaration: {accessibility}")
    print(f"Websites with errors: {errors}")
    
    print("\nAnalysis complete!")


if __name__ == "__main__":
    main()
