"""
Travel Cancellation Policy & Terms Checker
Covers: policy.1a, policy.1b, policy.2a, gdpr.1a, gdpr.1b, booking.1a, booking.1b

Checks whether a travel website:
  - Publishes cancellation/refund terms
  - Mentions 14-day right of withdrawal (Angrerettloven)
  - Links to general terms and conditions
  - Links to a privacy policy
  - Has a cookie/consent banner
  - Has a visible booking CTA

Legal basis: Angrerettloven §11/§22, Pakkereiseloven §31,
             GDPR Art. 13, ekomloven §2-7b
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


# Cancellation policy keywords (Bokmål + Nynorsk + English)
_CANCELLATION_RE = re.compile(
    r'\b(avbestilling|avbestillingspolicy|avbestillingsvilkår'
    r'|avbestillingsrett|avbestillingsfrist'
    r'|refusjon|refunderbar|refusjonsvilkår'
    r'|kansellering|kanselleringsvilkår'
    r'|cancellation\s*(policy|terms|conditions)?'
    r'|refund\s*(policy|terms)?'
    r'|cancellation\s*fee)\b',
    re.IGNORECASE
)

# 14-day right of withdrawal (Angrerettloven)
_WITHDRAWAL_RE = re.compile(
    r'\b(angrerett|angrefrist|14[\s-]*dager?'
    r'|14[\s-]*day(s)?\s*(right|withdrawal|cooling)'
    r'|right\s*of\s*withdrawal'
    r'|withdrawal\s*period)\b',
    re.IGNORECASE
)

# Terms and conditions links
_TERMS_RE = re.compile(
    r'\b(vilkår(\s*og\s*betingelser)?|betingelser|salgsvilkår'
    r'|kjøpsvilkår|reisevilkår|brukervilkår'
    r'|terms(\s*(and|&)\s*conditions)?'
    r'|terms\s*of\s*(service|use|sale)'
    r'|booking\s*conditions)\b',
    re.IGNORECASE
)

# Privacy policy
_PRIVACY_RE = re.compile(
    r'\b(personvernerklæring|personvern(spolicy)?'
    r'|personvernregler|privacy\s*policy'
    r'|personopplysninger|databeskyttelse'
    r'|data\s*protection\s*policy)\b',
    re.IGNORECASE
)

# Cookie / consent banner indicators
_COOKIE_RE = re.compile(
    r'\b(informasjonskaps(el|ler)|cookie(s)?|cookiepolicy'
    r'|cookie\s*consent|godta\s*(cookies?|informasjonskaps)'
    r'|cookie\s*banner|samtykke\s*til\s*cookies?'
    r'|vi\s*bruker\s*cookies?|accept\s*cookies?)\b',
    re.IGNORECASE
)

# Booking CTA keywords
_BOOKING_CTA_RE = re.compile(
    r'\b(bestill\s*(nå|her|tur|reise)?|book\s*(now|here|trip)?'
    r'|kjøp\s*(billett|tur)?|reserver\s*(plass|nå)?'
    r'|se\s*priser|vis\s*priser|sjekk\s*tilgjengelighet'
    r'|check\s*availability|buy\s*(ticket|now)'
    r'|book\s*online)\b',
    re.IGNORECASE
)

# Online booking form indicators
_ONLINE_BOOKING_RE = re.compile(
    r'\b(bestillingsskjema|booking\s*form|online\s*booking'
    r'|bestill\s*online|book\s*online|nettbestilling'
    r'|<form|checkout|handlekurv|cart)\b',
    re.IGNORECASE
)


def _find_link_by_text(soup: BeautifulSoup, pattern: re.Pattern):
    """Return first <a> tag whose text or href matches pattern."""
    for a in soup.find_all("a", href=True):
        if pattern.search(a.get_text(strip=True)) or pattern.search(a.get("href", "")):
            return a
    return None


def check_cancellation_policy(soup: BeautifulSoup, url: str, html: str = None) -> tuple:
    """
    Check cancellation policy, terms, GDPR, and booking CTA presence.
    Returns (issues, passed_checks, warnings).
    """
    issues = []
    passed = []
    warnings = []

    text = soup.get_text(separator=" ", strip=True)
    raw = html or ""

    # ── Rule policy.1a: cancellation policy present ───────────────────────────
    has_cancellation = bool(_CANCELLATION_RE.search(text))
    cancel_link = _find_link_by_text(soup, _CANCELLATION_RE)

    if has_cancellation or cancel_link:
        el_str = str(cancel_link)[:150] if cancel_link else "<text block>"
        passed.append("Avbestillingsvilkår funnet på siden (policy.1a)")
    else:
        issues.append(Issue(
            rule_id="policy.1a",
            criterion_id="policy.1",
            criterion_name="Avbestillingsvilkår",
            criterion_name_en="Cancellation policy",
            level="required",
            impact="serious",
            element="<footer> / <vilkår-side>",
            selector="footer a, nav a",
            issue="Ingen avbestillingsvilkår eller avbestillingspolicy funnet på siden",
            fix="Publiser tydelige avbestillingsvilkår og lenk til dem fra footer og bestillingsflyt. "
                "Hjemmel: Angrerettloven §11, Pakkereiseloven §31.",
            context=url,
        ))

    # ── Rule policy.1b: 14-day withdrawal right mentioned ────────────────────
    has_withdrawal = bool(_WITHDRAWAL_RE.search(text))

    if has_withdrawal:
        passed.append("14-dagers angrerett nevnt (policy.1b)")
    else:
        issues.append(Issue(
            rule_id="policy.1b",
            criterion_id="policy.1",
            criterion_name="Avbestillingsvilkår",
            criterion_name_en="Cancellation policy",
            level="required",
            impact="serious",
            element="<vilkår-side>",
            selector="body",
            issue="14-dagers angrerett (Angrerettloven) er ikke nevnt på siden",
            fix="Informer kundene om 14-dagers angreretten ved nettkjøp der den gjelder. "
                "Merk: pakketurer er unntatt, men dette må da opplyses eksplisitt. "
                "Hjemmel: Angrerettloven §22.",
            context=url,
        ))

    # ── Rule policy.2a: terms and conditions linked ───────────────────────────
    terms_link = _find_link_by_text(soup, _TERMS_RE)
    has_terms_text = bool(_TERMS_RE.search(text))

    if terms_link:
        passed.append(f"Vilkår og betingelser lenket til (policy.2a): '{terms_link.get_text(strip=True)[:50]}'")
    elif has_terms_text:
        passed.append("Vilkår og betingelser nevnt i tekst (policy.2a) — vurder å lage dedikert lenke")
    else:
        issues.append(Issue(
            rule_id="policy.2a",
            criterion_id="policy.2",
            criterion_name="Vilkår og betingelser",
            criterion_name_en="Terms and conditions",
            level="required",
            impact="moderate",
            element="<footer>",
            selector="footer a",
            issue="Ingen lenke til vilkår og betingelser funnet på siden",
            fix="Legg til en lenke til 'Vilkår og betingelser' eller 'Kjøpsvilkår' i footer. "
                "Hjemmel: Avtaleloven — vilkår må være tilgjengelige før kjøp.",
            context=url,
        ))

    # ── Rule gdpr.1a: privacy policy linked ──────────────────────────────────
    privacy_link = _find_link_by_text(soup, _PRIVACY_RE)
    has_privacy_text = bool(_PRIVACY_RE.search(text))

    if privacy_link:
        passed.append(f"Personvernerklæring lenket til (gdpr.1a): '{privacy_link.get_text(strip=True)[:50]}'")
    elif has_privacy_text:
        warnings.append(
            "Personvern nevnt i tekst men ingen dedikert lenke funnet (gdpr.1a) — "
            "legg til klikk-lenke i footer"
        )
    else:
        issues.append(Issue(
            rule_id="gdpr.1a",
            criterion_id="gdpr.1",
            criterion_name="Personvern",
            criterion_name_en="Privacy",
            level="required",
            impact="serious",
            element="<footer>",
            selector="footer a",
            issue="Ingen lenke til personvernerklæring funnet på siden",
            fix="Legg til en synlig lenke til personvernerklæringen i footer. "
                "Hjemmel: GDPR Art. 13 — behandlingsansvarlig må informere om databehandling.",
            context=url,
        ))

    # ── Rule gdpr.1b: cookie consent banner ──────────────────────────────────
    # Check both page text and raw HTML (banner may be injected by script)
    has_cookie_in_text = bool(_COOKIE_RE.search(text))
    has_cookie_in_html = bool(_COOKIE_RE.search(raw))

    # Also look for common consent management platform (CMP) script tags
    cmp_scripts = soup.find_all("script", src=re.compile(
        r'(cookiebot|cookieconsent|cookieyes|onetrust|consentmanager|klaro|tarteaucitron)',
        re.IGNORECASE
    ))

    if has_cookie_in_text or has_cookie_in_html or cmp_scripts:
        passed.append("Informasjonskapsel-samtykke / cookie-banner funnet (gdpr.1b)")
    else:
        issues.append(Issue(
            rule_id="gdpr.1b",
            criterion_id="gdpr.1",
            criterion_name="Personvern",
            criterion_name_en="Privacy",
            level="required",
            impact="serious",
            element="<body> (first load)",
            selector="body",
            issue="Ingen cookie-samtykkesbanner eller CMP-script funnet på siden",
            fix="Implementer et cookie-samtykkeverktøy (f.eks. Cookiebot, CookieYes, OneTrust) "
                "som ber om samtykke før ikke-nødvendige cookies settes. "
                "Hjemmel: ekomloven §2-7b, GDPR Art. 6.",
            context=url,
        ))

    # ── Rule booking.1a: booking CTA on homepage ─────────────────────────────
    cta_elements = soup.find_all(
        lambda tag: tag.name in ["a", "button"] and
        _BOOKING_CTA_RE.search(tag.get_text(strip=True))
    )

    if cta_elements:
        first_cta = cta_elements[0].get_text(strip=True)[:60]
        passed.append(f"Bestillingsknapp / CTA funnet (booking.1a): '{first_cta}'")
    else:
        issues.append(Issue(
            rule_id="booking.1a",
            criterion_id="booking.1",
            criterion_name="Bestillingsopplevelse",
            criterion_name_en="Booking experience",
            level="recommended",
            impact="moderate",
            element="<main>, <header>",
            selector="main a, header a, .cta, .booking-btn",
            issue="Ingen tydelig bestillingsknapp (CTA) funnet på siden",
            fix="Legg til en fremtredende 'Bestill nå'- eller 'Book'-knapp synlig uten scrolling. "
                "Dette er god praksis for reiselivssider og øker konverteringsraten.",
            context=url,
        ))

    # ── Rule booking.1b: online booking possible ─────────────────────────────
    has_online_booking = bool(_ONLINE_BOOKING_RE.search(raw or text))

    if has_online_booking:
        passed.append("Online bestilling / bestillingsskjema funnet (booking.1b)")
    else:
        warnings.append(
            "Ingen online bestillingsmulig het funnet (booking.1b) — "
            "nettstedet ser ut til å kun tilby kontakt via telefon/e-post. "
            "Vurder å implementere online booking for bedre kundeopplevelse."
        )

    return issues, passed, warnings
