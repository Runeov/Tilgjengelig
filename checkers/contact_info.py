"""
Travel Contact Information Checker
Covers: contact.1a, contact.1b, contact.1c

Checks whether a travel website provides the legally required contact
information: Norwegian phone number, email / contact form, and physical address.

Legal basis: Markedsføringsloven §6, ehandelsloven §8
"""

import re
from bs4 import BeautifulSoup
from dataclasses import dataclass


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


# Norwegian phone: 8 digits, optionally prefixed with +47 / 0047
# Covers formats: 77 12 34 56 / 77123456 / +47 77 12 34 56
_PHONE_RE = re.compile(
    r'(\+47|0047)?\s*'
    r'([2-9]\d)\s*'          # First two digits (no 0x prefix)
    r'(\d{2}\s*){3}',        # Remaining 6 digits in groups
    re.IGNORECASE
)

# Simpler fallback: any 8-digit sequence (local Norwegian format)
_PHONE_SIMPLE_RE = re.compile(r'\b[2-9]\d{7}\b')

# Email address
_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

# Norwegian postal code + city (5-digit postal code)
_ADDRESS_RE = re.compile(r'\b\d{4}\s+[A-ZÆØÅ][a-zæøå]+\b')

# Norwegian street address patterns
_STREET_RE = re.compile(
    r'\b[A-ZÆØÅ][a-zæøå]+(veien|vegen|gata|gaten|gate|vei|veg|stien|sti'
    r'|plassen|plass|torget|torg|allé|allé|bygda|senteret)\b',
    re.IGNORECASE
)

# Contact form / contact page link keywords
_CONTACT_FORM_RE = re.compile(
    r'\b(kontakt\s*oss|kontaktskjema|send\s*melding|contact\s*us|contact\s*form'
    r'|skriv\s*til\s*oss|ta\s*kontakt)\b',
    re.IGNORECASE
)


def _find_phone_element(soup: BeautifulSoup):
    """Return the first element containing a phone number, or None."""
    for tag in soup.find_all(["a", "p", "span", "div", "li", "td"]):
        text = tag.get_text(strip=True)
        if _PHONE_RE.search(text) or _PHONE_SIMPLE_RE.search(text):
            return tag
    return None


def _find_email_element(soup: BeautifulSoup):
    """Return first mailto link or element containing an email address."""
    mailto = soup.find("a", href=re.compile(r'^mailto:', re.IGNORECASE))
    if mailto:
        return mailto
    for tag in soup.find_all(["p", "span", "div", "li", "td", "a"]):
        if _EMAIL_RE.search(tag.get_text(strip=True)):
            return tag
    return None


def check_contact_info(soup: BeautifulSoup, url: str, html: str = None) -> tuple:
    """
    Check travel site contact information completeness.
    Returns (issues, passed_checks, warnings).
    """
    issues = []
    passed = []
    warnings = []

    text = soup.get_text(separator=" ", strip=True)

    # ── Rule contact.1a: Norwegian phone number ───────────────────────────────
    phone_el = _find_phone_element(soup)
    if phone_el:
        passed.append(f"Norsk telefonnummer funnet (contact.1a): '{phone_el.get_text(strip=True)[:40]}'")
    else:
        issues.append(Issue(
            rule_id="contact.1a",
            criterion_id="contact.1",
            criterion_name="Kontaktinformasjon",
            criterion_name_en="Contact information",
            level="required",
            impact="moderate",
            element="<header>, <footer>",
            selector="header, footer",
            issue="Ingen norsk telefonnummer funnet på siden",
            fix="Legg til et synlig norsk telefonnummer (format: 77 XX XX XX eller +47 XX XX XX XX) "
                "i header eller footer. Hjemmel: ehandelsloven §8 og Markedsføringsloven §6.",
            context=url,
        ))

    # ── Rule contact.1b: Email or contact form ────────────────────────────────
    email_el = _find_email_element(soup)
    has_contact_form = bool(_CONTACT_FORM_RE.search(text))

    if email_el:
        passed.append(f"E-postadresse funnet (contact.1b): '{email_el.get_text(strip=True)[:60]}'")
    elif has_contact_form:
        passed.append("Kontaktskjema funnet på siden (contact.1b)")
    else:
        issues.append(Issue(
            rule_id="contact.1b",
            criterion_id="contact.1",
            criterion_name="Kontaktinformasjon",
            criterion_name_en="Contact information",
            level="required",
            impact="moderate",
            element="<footer>",
            selector="footer",
            issue="Ingen e-postadresse eller kontaktskjema funnet på siden",
            fix="Legg til en synlig e-postadresse (eller lenk til kontaktskjema) i footer eller "
                "på kontaktsiden. Hjemmel: ehandelsloven §8.",
            context=url,
        ))

    # ── Rule contact.1c: Physical address ────────────────────────────────────
    has_postal = bool(_ADDRESS_RE.search(text))
    has_street = bool(_STREET_RE.search(text))

    if has_postal or has_street:
        passed.append("Fysisk adresse / postnummer funnet (contact.1c)")
    else:
        # Only a warning — recommended, not required
        issues.append(Issue(
            rule_id="contact.1c",
            criterion_id="contact.1",
            criterion_name="Kontaktinformasjon",
            criterion_name_en="Contact information",
            level="recommended",
            impact="minor",
            element="<footer>",
            selector="footer",
            issue="Ingen fysisk adresse eller postnummer funnet på siden",
            fix="Legg til besøks- eller postadresse (gateadresse + postnummer + sted) i footer. "
                "Dette øker tilliten og er anbefalt av ehandelsloven §8.",
            context=url,
        ))

    # ── Extra: check if contact info is in footer specifically ───────────────
    footer = soup.find("footer")
    if footer:
        footer_text = footer.get_text(separator=" ", strip=True)
        if not (_PHONE_RE.search(footer_text) or _PHONE_SIMPLE_RE.search(footer_text)):
            if phone_el:
                warnings.append(
                    "Telefonnummer funnet, men ikke i <footer> — vurder å flytte det dit "
                    "for bedre synlighet og samsvar med konvensjon (contact.1a)"
                )
    else:
        warnings.append(
            "Ingen <footer>-element funnet — kontaktinformasjon bør ligge i en semantisk footer"
        )

    return issues, passed, warnings
