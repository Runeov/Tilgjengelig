"""
Travel Regulatory Identity Checker
Covers: org.1a, org.2a, content.1a, content.1b

Checks whether a travel website:
  - Displays its Norwegian organisation number (org.nr.)
  - Mentions Reisegarantifondet / travel guarantee (for package tour operators)
  - Is available in Norwegian (Språkloven compliance)
  - Also offers English (quality signal for tourism)

Also performs a live lookup against the Brønnøysund Register Centre
(data.brreg.no) if an org.nr is found, to verify the company is active.

Legal basis: Enhetsregisterloven §21, Markedsføringsloven §6,
             Pakkereiseloven §55, Språkloven §17
"""

import re
import json
from dataclasses import dataclass

try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

from bs4 import BeautifulSoup


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


# Norwegian org.nr: 9 digits, optionally labelled
_ORG_NR_RE = re.compile(
    r'\b(org\.?\s*nr\.?\s*:?\s*|organisasjonsnummer\s*:?\s*|orgnr\s*:?\s*)?'
    r'(\d{3}[\s\-]?\d{3}[\s\-]?\d{3})\b',
    re.IGNORECASE
)

# Reisegarantifondet / travel guarantee indicators
_TRAVEL_GUARANTEE_RE = re.compile(
    r'\b(reisegarantifondet|reisegaranti|rfg\.?\s*nr'
    r'|godkjent\s*(reisearrangør|turoperatør)'
    r'|pakkereis(e|lov)'
    r'|travel\s*guarantee\s*fund'
    r'|atol\s*protected)\b',
    re.IGNORECASE
)

# Norwegian language indicators
_NORWEGIAN_RE = re.compile(
    r'(<html[^>]*lang\s*=\s*["\']?(nb|nn|no)["\']?'
    r'|<meta[^>]*language[^>]*content\s*=\s*["\']?(nb|nn|no)["\']?)',
    re.IGNORECASE
)

# English language availability indicators
_ENGLISH_RE = re.compile(
    r'(<html[^>]*lang\s*=\s*["\']?en["\']?'
    r'|hreflang\s*=\s*["\']?en["\']?'
    r'|<a[^>]*>(english|in\s*english|eng)\s*</a>'
    r'|<option[^>]*>(english|english\s*language)\s*</option>)',
    re.IGNORECASE
)

# Language switcher UI elements
_LANG_SWITCH_RE = re.compile(
    r'\b(english|in\s*english|switch\s*(to\s*)?(english|language)'
    r'|språkvalg|change\s*language)\b',
    re.IGNORECASE
)

BRREG_API = "https://data.brreg.no/enhetsregisteret/api/enheter/{org_nr}"


def _extract_org_nr(text: str) -> str | None:
    """Extract a 9-digit org.nr from page text, return digits-only string or None."""
    match = _ORG_NR_RE.search(text)
    if match:
        digits = re.sub(r'[\s\-]', '', match.group(2))
        if len(digits) == 9:
            return digits
    return None


def _lookup_brreg(org_nr: str) -> dict:
    """
    Query Brønnøysund Register Centre for company status.
    Returns dict with keys: found, name, active, org_form, error
    """
    if not _REQUESTS_AVAILABLE:
        return {"found": False, "error": "requests not available"}
    try:
        resp = _requests.get(
            BRREG_API.format(org_nr=org_nr),
            timeout=8,
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "found": True,
                "name": data.get("navn", ""),
                "active": not data.get("konkurs", False) and not data.get("underAvvikling", False),
                "org_form": data.get("organisasjonsform", {}).get("kode", ""),
                "municipality": data.get("forretningsadresse", {}).get("kommune", ""),
                "error": None,
            }
        elif resp.status_code == 404:
            return {"found": False, "error": "Org.nr ikke funnet i Enhetsregisteret"}
        else:
            return {"found": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"found": False, "error": str(e)}


def check_regulatory(soup: BeautifulSoup, url: str, html: str = None) -> tuple:
    """
    Check regulatory identity, travel guarantee, and language compliance.
    Returns (issues, passed_checks, warnings).
    """
    issues = []
    passed = []
    warnings = []

    text = soup.get_text(separator=" ", strip=True)
    raw = html or ""

    # ── Rule org.1a: org.nr visible on page ───────────────────────────────────
    org_nr = _extract_org_nr(text)

    if org_nr:
        passed.append(f"Organisasjonsnummer funnet på siden (org.1a): {org_nr[:3]} {org_nr[3:6]} {org_nr[6:]}")

        # ── Bonus: live Brønnøysund lookup ────────────────────────────────────
        brreg = _lookup_brreg(org_nr)
        if brreg["found"]:
            if brreg["active"]:
                passed.append(
                    f"Brønnøysund-oppslag bekreftet: '{brreg['name']}' er aktivt registrert "
                    f"({brreg['org_form']}) i {brreg.get('municipality', 'ukjent kommune')}"
                )
            else:
                issues.append(Issue(
                    rule_id="org.1a",
                    criterion_id="org.1",
                    criterion_name="Regulatorisk identitet",
                    criterion_name_en="Regulatory identity",
                    level="required",
                    impact="critical",
                    element=f"org.nr {org_nr}",
                    selector="footer",
                    issue=f"Org.nr {org_nr} er registrert i Enhetsregisteret, men virksomheten "
                          f"er under avvikling eller konkurs iflg. Brønnøysund",
                    fix="Kontroller selskapets status. Kunder bør advares dersom operatøren er under avvikling.",
                    context=url,
                ))
        elif brreg["error"] and "ikke funnet" in brreg["error"]:
            issues.append(Issue(
                rule_id="org.1a",
                criterion_id="org.1",
                criterion_name="Regulatorisk identitet",
                criterion_name_en="Regulatory identity",
                level="required",
                impact="serious",
                element=f"org.nr {org_nr}",
                selector="footer",
                issue=f"Org.nr {org_nr} ble ikke funnet i Brønnøysundregistrene",
                fix="Verifiser at korrekt organisasjonsnummer er oppgitt på nettsiden. "
                    "Hjemmel: Enhetsregisterloven §21.",
                context=url,
            ))
        else:
            warnings.append(
                f"Brønnøysund-oppslag mislyktes for org.nr {org_nr}: {brreg.get('error', 'ukjent feil')}"
            )
    else:
        issues.append(Issue(
            rule_id="org.1a",
            criterion_id="org.1",
            criterion_name="Regulatorisk identitet",
            criterion_name_en="Regulatory identity",
            level="required",
            impact="serious",
            element="<footer>",
            selector="footer",
            issue="Organisasjonsnummer (org.nr.) ikke funnet på siden",
            fix="Legg til org.nr. tydelig i footer, f.eks. 'Org.nr.: 123 456 789'. "
                "Hjemmel: Enhetsregisterloven §21 og Markedsføringsloven §6.",
            context=url,
        ))

    # ── Rule org.2a: travel guarantee (Pakkereiseloven) ───────────────────────
    has_travel_guarantee = bool(_TRAVEL_GUARANTEE_RE.search(text))

    # Only flag if the site looks like a tour operator / package travel site
    _PACKAGE_TOUR_RE = re.compile(
        r'\b(pakke(reise|tur)|rundreise|all[\s-]*inclusive|guidet\s*(tur|reise)'
        r'|charter(reise|fly)?|arrangement|gruppereise)\b',
        re.IGNORECASE
    )
    is_tour_operator = bool(_PACKAGE_TOUR_RE.search(text))

    if is_tour_operator:
        if has_travel_guarantee:
            passed.append("Reisegaranti / Reisegarantifondet nevnt for pakkereisearrangør (org.2a)")
        else:
            issues.append(Issue(
                rule_id="org.2a",
                criterion_id="org.2",
                criterion_name="Reisegodkjenning",
                criterion_name_en="Travel operator approval",
                level="required",
                impact="critical",
                element="<footer> / <om-oss>",
                selector="footer",
                issue="Siden ser ut til å selge pakketurer, men ingen reisegaranti eller "
                      "Reisegarantifondet-godkjenning er nevnt",
                fix="Pakkereisearrangører er pliktige til å stille reisegaranti iflg. "
                    "Pakkereiseloven §55. Legg til RGF-godkjenningsnummer og lenk til "
                    "https://www.reisegarantifondet.no i footer.",
                context=url,
            ))
    else:
        passed.append("Ingen pakkereisetegn funnet — org.2a ikke aktuelt for denne siden")

    # ── Rule content.1a: Norwegian language ──────────────────────────────────
    has_norwegian_lang = bool(_NORWEGIAN_RE.search(raw))

    if has_norwegian_lang:
        passed.append("Nettstedet er merket som norskspråklig i HTML (content.1a)")
    else:
        # Fallback: check if text contains common Norwegian words
        _NOR_WORDS_RE = re.compile(
            r'\b(og|er|ikke|til|av|på|med|for|som|en|et|den|det|de)\b',
            re.IGNORECASE
        )
        nor_word_count = len(_NOR_WORDS_RE.findall(text[:2000]))
        if nor_word_count > 15:
            warnings.append(
                "Siden ser ut til å være på norsk, men mangler lang-attributt i <html>-taggen (content.1a). "
                "Legg til <html lang=\"nb\"> for Bokmål eller <html lang=\"nn\"> for Nynorsk. "
                "Hjemmel: Språkloven §17 — offentlig støttede virksomheter skal bruke norsk."
            )
        else:
            issues.append(Issue(
                rule_id="content.1a",
                criterion_id="content.1",
                criterion_name="Innholdskvalitet",
                criterion_name_en="Content quality",
                level="recommended",
                impact="moderate",
                element="<html>",
                selector="html",
                issue="Siden mangler norsk lang-attributt og ser ikke ut til å ha norsk innhold",
                fix="Sett lang=\"nb\" på <html>-elementet og sørg for at innholdet er tilgjengelig "
                    "på norsk. Hjemmel: Språkloven §17.",
                context=url,
            ))

    # ── Rule content.1b: English language available ───────────────────────────
    has_english = bool(_ENGLISH_RE.search(raw)) or bool(_LANG_SWITCH_RE.search(text))

    if has_english:
        passed.append("Engelsk språkalternativ funnet (content.1b)")
    else:
        warnings.append(
            "Ingen engelsk versjon eller språkbytter funnet (content.1b) — "
            "for reiselivsbedrifter i Finnmark er engelsk viktig for internasjonale turister "
            "(nordlys-turister, cruisepassasjerer). Vurder å legge til en engelsk versjon."
        )

    return issues, passed, warnings
