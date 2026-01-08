"""
WCAG 3.1.1 Language Checker
Checks page language is specified.
"""

from bs4 import BeautifulSoup

RULE_INFO = {
    "3.1.1a": {
        "criterion": "3.1.1",
        "criterion_name": "Språk på siden",
        "criterion_name_en": "Language of Page",
        "level": "A",
    }
}

# Valid ISO 639-1 language codes
VALID_LANG_CODES = {
    'aa', 'ab', 'ae', 'af', 'ak', 'am', 'an', 'ar', 'as', 'av', 'ay', 'az',
    'ba', 'be', 'bg', 'bh', 'bi', 'bm', 'bn', 'bo', 'br', 'bs', 
    'ca', 'ce', 'ch', 'co', 'cr', 'cs', 'cu', 'cv', 'cy',
    'da', 'de', 'dv', 'dz',
    'ee', 'el', 'en', 'eo', 'es', 'et', 'eu',
    'fa', 'ff', 'fi', 'fj', 'fo', 'fr', 'fy',
    'ga', 'gd', 'gl', 'gn', 'gu', 'gv',
    'ha', 'he', 'hi', 'ho', 'hr', 'ht', 'hu', 'hy', 'hz',
    'ia', 'id', 'ie', 'ig', 'ii', 'ik', 'io', 'is', 'it', 'iu',
    'ja', 'jv',
    'ka', 'kg', 'ki', 'kj', 'kk', 'kl', 'km', 'kn', 'ko', 'kr', 'ks', 'ku', 'kv', 'kw', 'ky',
    'la', 'lb', 'lg', 'li', 'ln', 'lo', 'lt', 'lu', 'lv',
    'mg', 'mh', 'mi', 'mk', 'ml', 'mn', 'mr', 'ms', 'mt', 'my',
    'na', 'nb', 'nd', 'ne', 'ng', 'nl', 'nn', 'no', 'nr', 'nv', 'ny',
    'oc', 'oj', 'om', 'or', 'os',
    'pa', 'pi', 'pl', 'ps', 'pt',
    'qu',
    'rm', 'rn', 'ro', 'ru', 'rw',
    'sa', 'sc', 'sd', 'se', 'sg', 'si', 'sk', 'sl', 'sm', 'sn', 'so', 'sq', 'sr', 'ss', 'st', 'su', 'sv', 'sw',
    'ta', 'te', 'tg', 'th', 'ti', 'tk', 'tl', 'tn', 'to', 'tr', 'ts', 'tt', 'tw', 'ty',
    'ug', 'uk', 'ur', 'uz',
    've', 'vi', 'vo',
    'wa', 'wo',
    'xh',
    'yi', 'yo',
    'za', 'zh', 'zu'
}


def check_language(soup, url, **kwargs):
    """
    Check that page language is properly specified.
    
    Returns tuple of (issues, passed, warnings).
    """
    issues = []
    passed = []
    warnings = []
    
    rule = RULE_INFO["3.1.1a"]
    
    # Find html element
    html = soup.find('html')
    
    if not html:
        issues.append({
            "rule_id": "3.1.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "serious",
            "element": "<html>",
            "selector": "html",
            "issue": "Kan ikke finne <html> element",
            "fix": "Sørg for at siden har gyldig HTML-struktur"
        })
        return issues, passed, warnings
    
    # Check lang attribute
    lang = html.get('lang', '').strip()
    xml_lang = html.get('xml:lang', '').strip()
    
    effective_lang = lang or xml_lang
    
    if not effective_lang:
        issues.append({
            "rule_id": "3.1.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "serious",
            "element": str(html)[:100],
            "selector": "html",
            "issue": "Siden mangler språkattributt (lang) på <html>-elementet",
            "fix": "Legg til lang-attributt, f.eks. <html lang='no'> eller <html lang='nb'>"
        })
    else:
        # Validate language code
        lang_code = effective_lang.split('-')[0].lower()
        
        if lang_code not in VALID_LANG_CODES:
            issues.append({
                "rule_id": "3.1.1a",
                "criterion_id": rule["criterion"],
                "criterion_name": rule["criterion_name"],
                "criterion_name_en": rule["criterion_name_en"],
                "level": rule["level"],
                "impact": "moderate",
                "element": f"<html lang='{effective_lang}'>",
                "selector": "html",
                "issue": f"Ugyldig språkkode: '{effective_lang}'",
                "fix": "Bruk gyldig ISO 639-1 språkkode (f.eks. 'no', 'nb', 'nn', 'en')"
            })
        else:
            passed.append({
                "rule_id": "3.1.1a",
                "criterion_id": rule["criterion"],
                "criterion_name": rule["criterion_name"],
                "message": f"Sidespråk er angitt: {effective_lang}"
            })
    
    # Check for inconsistency between lang and xml:lang
    if lang and xml_lang and lang.lower() != xml_lang.lower():
        warnings.append({
            "rule_id": "3.1.1a",
            "criterion_id": rule["criterion"],
            "criterion_name": rule["criterion_name"],
            "criterion_name_en": rule["criterion_name_en"],
            "level": rule["level"],
            "impact": "minor",
            "element": f"<html lang='{lang}' xml:lang='{xml_lang}'>",
            "selector": "html",
            "issue": f"Inkonsistens mellom lang ('{lang}') og xml:lang ('{xml_lang}')",
            "fix": "Bruk samme språkkode for begge attributter"
        })
    
    return issues, passed, warnings
