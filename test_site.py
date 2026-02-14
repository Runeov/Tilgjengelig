import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

base_url = 'https://hamsunsenteret.no'
headers = {'User-Agent': 'WCAGChecker/1.0'}

try:
    resp = requests.get(base_url, headers=headers, timeout=30)
    print(f'Status: {resp.status_code}')
    print(f'URL: {resp.url}')
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Find all links
    links = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
            continue
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.netloc == urlparse(base_url).netloc:
            clean_url = f'{parsed.scheme}://{parsed.netloc}{parsed.path}'
            links.add(clean_url)
    
    print(f'\nFound {len(links)} unique internal links:')
    for link in sorted(links)[:50]:
        print(f'  {link}')
    
    # Print page title
    print(f'\nPage title: {soup.title.string if soup.title else "No title"}')
    
    # Print all anchor tags for debugging
    print('\n\nAll anchor tags:')
    for a in soup.find_all('a', href=True)[:20]:
        print(f'  href={a["href"]}, text={a.get_text(strip=True)[:50]}')
    
    # Print body content length
    print(f'\nHTML content length: {len(resp.text)}')
    print(f'Body tag found: {soup.body is not None}')
    
    # Print first 2000 chars of HTML
    print('\n\nFirst 2000 chars of HTML:')
    print(resp.text[:2000])
    
    # Check if content is dynamically loaded
    print('\n\nChecking for Vue/React root elements:')
    print(f'  #app found: {soup.find(id="app") is not None}')
    print(f'  #root found: {soup.find(id="root") is not None}')
    print(f'  .wips-app found: {soup.find(class_="wips-app") is not None}')
    
    # Check for WipsApp
    print(f'\n  WipsApp in scripts: {"WipsApp" in resp.text}')
    
    # Print body content
    print('\n\nBody content (first 3000 chars):')
    if soup.body:
        body_str = soup.body.prettify()[:3000]
        print(body_str)
        # Save full HTML to file for inspection
        with open('hamsunsenteret_html.html', 'w', encoding='utf-8') as f:
            f.write(resp.text)
        print('\n\nFull HTML saved to hamsunsenteret_html.html')
    else:
        print('No body tag found')
except Exception as e:
    print(f'Error: {e}')
