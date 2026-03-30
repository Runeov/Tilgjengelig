"""
Travel Pricing Transparency Checker
Covers: price.1a, price.1b, price.2a

Checks whether a travel website displays prices with clear VAT status
and has visible pricing before the booking step.

Legal basis: Markedsføringsloven §7, Prisopplysningsforskriften §3,
             Pakkereiseloven §28
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


# Norwegian + English price patterns
_PRICE_RE = re.compile(
    r'(\b\d[\d\s]*[\.,]\d{2}\s*(kr|NOK|,-)\b'      # 1.299,00 kr / 1299,- NOK
    r'|\b\d[\d\s]{2,}\s*(kr|NOK|,-)\b'              # 1 299 kr / 850,-
    r'|\b(fra|from|pris|price)\s+\d+)',              # fra 499 / from 499
    re.IGNORECASE
)

# VAT / tax indicator patterns
_VAT_RE = re.compile(
    r'\b(inkl\.?\s*mva|ekskl\.?\s*mva|incl\.?\s*vat|excl\.?\s*vat'
    r'|inkludert\s*merverdiavgift|eksklusive\s*mva'
    r'|mva\s*inkludert|mva\s*ikke\s*inkludert'
    r'|ink\.\s*mva|eks\.\s*mva'
    r'|inc\.\s*tax|excl\.\s*tax'
    r'|tax\s*included|tax\s*excluded)\b',
    re.IGNORECASE
)

# Booking / checkout trigger words
_BOOKING_RE = re.compile(
    r'\b(bestill|book|kjøp|buy|reserver|reserve|checkout|betaling|payment|kasse|cart)\b',
    re.IGNORECASE
)

# Privacy / GDPR cookie keywords used across checkers
_PRIVACY_RE = re.compile(
    r'\b(personvern|personvernerklæring|privacy\s*policy|cookie|informasjonskaps|samtykke|consent)\b',
    re.IGNORECASE
)


def check_pricing(soup: BeautifulSoup, url: str, html: str = None) -> tuple:
    """
    Check travel site pricing transparency.
    Returns (issues, passed_checks, warnings).
    """
    issues = []
    passed = []
    warnings = []

    text = soup.get_text(separator=" ", strip=True)
    raw = html or ""

    has_prices = bool(_PRICE_RE.search(text))
    has_vat_info = bool(_VAT_RE.search(text))
    has_booking = bool(_BOOKING_RE.search(text))

    # ── Rule price.1a: prices must state VAT status ───────────────────────────
    if has_prices:
        if has_vat_info:
            passed.append("Priser er oppgitt med mva-status (price.1a)")
        else:
            # Find the first price element for context
            price_match = _PRICE_RE.search(text)
            context_snippet = price_match.group(0) if price_match else ""

            issues.append(Issue(
                rule_id="price.1a",
                criterion_id="price.1",
                criterion_name="Prisgjennomsiktighet",
                criterion_name_en="Price transparency",
                level="required",
                impact="serious",
                element=f'"{context_snippet}"',
                selector="body",
                issue="Priser vises uten tydelig angivelse av mva-status (inkl. eller ekskl. mva)",
                fix="Legg til 'inkl. mva' eller 'ekskl. mva' ved siden av alle priser. "
                    "Eksempel: 'Fra 999 kr inkl. mva'. Hjemmel: Prisopplysningsforskriften §3.",
                context=url,
            ))
    else:
        warnings.append("Ingen priser funnet på denne siden (price.1a) — kan være en informasjonsside")

    # ── Rule price.1b: total price visible before booking ────────────────────
    if has_booking:
        # Look for price near booking elements
        booking_elements = soup.find_all(
            lambda tag: tag.name in ["button", "a", "input"] and
            tag.get_text(strip=True) and
            _BOOKING_RE.search(tag.get_text(strip=True))
        )
        price_near_booking = False
        for el in booking_elements:
            # Check siblings and parent for price context
            parent_text = el.parent.get_text(separator=" ", strip=True) if el.parent else ""
            if _PRICE_RE.search(parent_text):
                price_near_booking = True
                break

        if price_near_booking:
            passed.append("Totalpris er synlig nær bestillingsknapp (price.1b)")
        else:
            issues.append(Issue(
                rule_id="price.1b",
                criterion_id="price.1",
                criterion_name="Prisgjennomsiktighet",
                criterion_name_en="Price transparency",
                level="required",
                impact="critical",
                element="<booking CTA>",
                selector="a, button",
                issue="Ingen tydelig totalpris funnet i nærheten av bestillingsknappen",
                fix="Vis totalprisen (inkl. alle avgifter og gebyrer) direkte ved siden av "
                    "bestillingsknappen. Hjemmel: Pakkereiseloven §28, Angrerettloven §8.",
                context=url,
            ))
    else:
        passed.append("Ingen bestillingsknapp funnet på denne siden — price.1b ikke aktuelt")

    # ── Rule price.2a: no booking-step fee surprise detection ─────────────────
    # Heuristic: look for fee-related words that appear only in fine print
    fee_patterns = re.compile(
        r'\b(gebyr|avgift|tillegg|surcharge|fee|booking\s*fee|service\s*fee|handling\s*fee)\b',
        re.IGNORECASE
    )
    if fee_patterns.search(text) and has_prices:
        # Check if fee mention is near a price — if not, it could be hidden
        warnings.append(
            "Gebyrer/avgifter nevnt på siden (price.2a) — verifiser manuelt at disse "
            "er inkludert i viste priser og ikke overrasker kunden ved betaling"
        )
    elif has_prices:
        passed.append("Ingen separate gebyrmerkinger funnet (price.2a)")

    return issues, passed, warnings
