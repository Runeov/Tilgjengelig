"""
WCAG Language Accessibility Checker
Covers: 3.1.1 Language of Page, 3.1.2 Language of Parts
"""

from dataclasses import dataclass
import re


@dataclass
class Issue:
    rule_id: str
    criterion_id: str
    criterion_name: str
    criterion_name_en: str
    level: str
    impact: str
    element: str
    selector: str
    issue: str
    fix: str
    context: str = ""


# Valid ISO 639-1 language codes (common ones)
VALID_LANG_CODES = {
    'aa', 'ab', 'ae', 'af', 'ak', 'am', 'an', 'ar', 'as', 'av', 'ay', 'az',
    'ba', 'be', 'bg', 'bh', 'bi', 'bm', 'bn', 'bo', 'br', 'bs', 'ca', 'ce',
    'ch', 'co', 'cr', 'cs', 'cu', 'cv', 'cy', 'da', 'de', 'dv', 'dz', 'ee',
    'el', 'en', 'eo', 'es', 'et', 'eu', 'fa', 'ff', 'fi', 'fj', 'fo', 'fr',
    'fy', 'ga', 'gd', 'gl', 'gn', 'gu', 'gv', 'ha', 'he', 'hi', 'ho', 'hr',
    'ht', 'hu', 'hy', 'hz', 'ia', 'id', 'ie', 'ig', 'ii', 'ik', 'io', 'is',
    'it', 'iu', 'ja', 'jv', 'ka', 'kg', 'ki', 'kj', 'kk', 'kl', 'km', 'kn',
    'ko', 'kr', 'ks', 'ku', 'kv', 'kw', 'ky', 'la', 'lb', 'lg', 'li', 'ln',
    'lo', 'lt', 'lu', 'lv', 'mg', 'mh', 'mi', 'mk', 'ml', 'mn', 'mr', 'ms',
    'mt', 'my', 'na', 'nb', 'nd', 'ne', 'ng', 'nl', 'nn', 'no', 'nr', 'nv',
    'ny', 'oc', 'oj', 'om', 'or', 'os', 'pa', 'pi', 'pl', 'ps', 'pt', 'qu',
    'rm', 'rn', 'ro', 'ru', 'rw', 'sa', 'sc', 'sd', 'se', 'sg', 'si', 'sk',
    'sl', 'sm', 'sn', 'so', 'sq', 'sr', 'ss', 'st', 'su', 'sv', 'sw', 'ta',
    'te', 'tg', 'th', 'ti', 'tk', 'tl', 'tn', 'to', 'tr', 'ts', 'tt', 'tw',
    'ty', 'ug', 'uk', 'ur', 'uz', 've', 'vi', 'vo', 'wa', 'wo', 'xh', 'yi',
    'yo', 'za', 'zh', 'zu'
}


def check_language(soup, url, html=None):
    """Check language attributes for accessibility."""
    issues = []
    passed = []
    warnings = []
    
    # Check html element for lang attribute
    html_elem = soup.find('html')
    
    if not html_elem:
        issues.append(Issue(
            rule_id="3.1.1",
            criterion_id="3.1.1",
            criterion_name="Språk på siden",
            criterion_name_en="Language of Page",
            level="A",
            impact="serious",
            element="<html>",
            selector="html",
            issue="No <html> element found",
            fix="Ensure page has proper HTML structure with <html> element"
        ))
        return issues, passed, warnings
    
    lang = html_elem.get('lang') or html_elem.get('xml:lang')
    
    if not lang:
        issues.append(Issue(
            rule_id="3.1.1",
            criterion_id="3.1.1",
            criterion_name="Språk på siden",
            criterion_name_en="Language of Page",
            level="A",
            impact="serious",
            element=str(html_elem)[:100],
            selector="html",
            issue="Page is missing language declaration",
            fix="Add lang attribute to <html> element (e.g., lang='nb' for Norwegian Bokmål)"
        ))
    else:
        # Validate lang code
        base_lang = lang.split('-')[0].lower()
        
        if base_lang not in VALID_LANG_CODES:
            issues.append(Issue(
                rule_id="3.1.1",
                criterion_id="3.1.1",
                criterion_name="Språk på siden",
                criterion_name_en="Language of Page",
                level="A",
                impact="serious",
                element=f'<html lang="{lang}">',
                selector="html",
                issue=f"Invalid language code: '{lang}'",
                fix="Use a valid ISO 639-1 language code (e.g., 'nb', 'nn', 'en')"
            ))
        elif len(lang) < 2:
            issues.append(Issue(
                rule_id="3.1.1",
                criterion_id="3.1.1",
                criterion_name="Språk på siden",
                criterion_name_en="Language of Page",
                level="A",
                impact="serious",
                element=f'<html lang="{lang}">',
                selector="html",
                issue=f"Language code too short: '{lang}'",
                fix="Use complete language code (e.g., 'nb' not just 'n')"
            ))
        else:
            passed.append(f"3.1.1: Page has valid language: {lang}")
    
    # Check for elements with lang attribute (language of parts)
    elements_with_lang = soup.find_all(lang=True)
    
    for elem in elements_with_lang:
        if elem.name == 'html':
            continue
        
        elem_lang = elem.get('lang')
        base_lang = elem_lang.split('-')[0].lower() if elem_lang else ''
        
        if base_lang and base_lang not in VALID_LANG_CODES:
            issues.append(Issue(
                rule_id="3.1.2",
                criterion_id="3.1.2",
                criterion_name="Språk på deler av innhold",
                criterion_name_en="Language of Parts",
                level="AA",
                impact="moderate",
                element=str(elem)[:200],
                selector=f'{elem.name}[lang="{elem_lang}"]',
                issue=f"Invalid language code on element: '{elem_lang}'",
                fix="Use a valid ISO 639-1 language code"
            ))
        else:
            passed.append(f"3.1.2: Element has language override: {elem_lang}")
    
    # Check for common foreign phrases that might need lang attribute
    if html:
        foreign_indicators = [
            (r'\b(lorem ipsum|dolor sit amet)\b', 'la', 'Latin placeholder text'),
            (r'\b(et al\.?|etc\.?|e\.g\.?|i\.e\.?)\b', 'la', 'Latin abbreviation'),
        ]
        
        for pattern, expected_lang, desc in foreign_indicators:
            if re.search(pattern, html, re.I):
                warnings.append(f"3.1.2: Page contains {desc} - consider using lang='{expected_lang}'")
    
    # Check for hreflang on links to other language versions
    for a in soup.find_all('a', hreflang=True):
        hreflang = a.get('hreflang')
        base_lang = hreflang.split('-')[0].lower() if hreflang else ''
        
        if base_lang and base_lang not in VALID_LANG_CODES:
            issues.append(Issue(
                rule_id="3.1.2",
                criterion_id="3.1.2",
                criterion_name="Språk på deler av innhold",
                criterion_name_en="Language of Parts",
                level="AA",
                impact="minor",
                element=str(a)[:200],
                selector=f'a[hreflang="{hreflang}"]',
                issue=f"Invalid hreflang code: '{hreflang}'",
                fix="Use a valid ISO 639-1 language code"
            ))
        else:
            passed.append(f"3.1.2: Link has valid hreflang: {hreflang}")
    
    return issues, passed, warnings
