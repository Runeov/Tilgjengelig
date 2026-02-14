#!/usr/bin/env python3
"""
Norwegian Legal Compliance Checker

Checks websites for compliance with:
  Module 1: Åpenhetsloven (Transparency Act)
  Module 2: Cookies / Ny Ekomlov & GDPR
  Module 3: CSRD Sustainability Reporting
  Module 4: European Accessibility Act (EAA)

Usage:
    python compliance_checker.py https://example.com
    python compliance_checker.py https://example.com --no-browser
    python compliance_checker.py https://example.com --format json
"""

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import requests

# Try to import browser fetching
try:
    from browser_fetch import fetch_page_with_browser, close_browser
    BROWSER_AVAILABLE = True
except ImportError:
    BROWSER_AVAILABLE = False


@dataclass
class ComplianceCheck:
    """A single compliance check result."""
    module: str           # e.g. "Åpenhetsloven", "Cookies", "CSRD", "EAA"
    check_id: str         # e.g. "transparency_report", "cookie_reject_button"
    title: str            # Short title
    title_no: str         # Norwegian title
    description: str      # What was checked
    passed: bool          # True = compliant
    severity: str         # critical, serious, moderate, info
    details: str = ""     # Additional context/evidence
    evidence: str = ""    # HTML snippet or URL found
    legal_basis: str = "" # Which law requires this


@dataclass
class ComplianceResult:
    """Full compliance result for a site."""
    url: str
    timestamp: str
    checks: list = field(default_factory=list)
    error: str = ""

    @property
    def summary(self):
        passed = sum(1 for c in self.checks if c.passed)
        failed = sum(1 for c in self.checks if not c.passed)
        by_module = {}
        for c in self.checks:
            if c.module not in by_module:
                by_module[c.module] = {"passed": 0, "failed": 0}
            if c.passed:
                by_module[c.module]["passed"] += 1
            else:
                by_module[c.module]["failed"] += 1
        return {
            "total_checks": len(self.checks),
            "passed": passed,
            "failed": failed,
            "score_pct": round(passed / len(self.checks) * 100) if self.checks else 0,
            "by_module": by_module,
        }


class ComplianceChecker:
    """Checks a website for Norwegian legal compliance beyond WCAG."""

    def __init__(self, use_browser=True, wait_for="load"):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ComplianceChecker/1.0 (Norwegian Legal Compliance Audit)"
        })
        self.use_browser = use_browser and BROWSER_AVAILABLE
        self.wait_for = wait_for

    def fetch_page(self, url):
        """Fetch page HTML, returns (html, final_url) or (None, None)."""
        if self.use_browser:
            try:
                result = fetch_page_with_browser(url, wait_for=self.wait_for)
                if result:
                    # browser_fetch returns (html, final_url) tuple
                    if isinstance(result, tuple) and len(result) >= 2:
                        html, final_url = result[0], result[1]
                        if html:
                            return html, final_url or url
                    elif isinstance(result, dict) and result.get("html"):
                        return result["html"], result.get("url", url)
            except Exception as e:
                print(f"  Browser fetch failed: {e}")

        # Fallback to requests
        try:
            resp = self.session.get(url, timeout=20, allow_redirects=True)
            resp.raise_for_status()
            return resp.text, resp.url
        except Exception as e:
            print(f"  HTTP fetch failed: {e}")
            return None, None

    def check_site(self, url):
        """Run all compliance checks on a site."""
        print(f"\nCompliance audit: {url}")
        print("-" * 60)

        result = ComplianceResult(
            url=url,
            timestamp=datetime.now().isoformat(),
        )

        # Fetch the main page
        html, final_url = self.fetch_page(url)
        if not html:
            result.error = "Could not fetch the website"
            return result

        soup = BeautifulSoup(html, "lxml")

        # Also try to find and fetch common subpages
        subpage_htmls = {}
        subpage_keywords = [
            "apenhetsloven", "openhetsloven", "aktsomhetsvurdering",
            "transparency", "barekraft", "sustainability",
            "personvern", "privacy", "cookies", "informasjonskapsler",
            "tilgjengelighet", "accessibility",
        ]
        links = soup.find_all("a", href=True)
        found_subpages = set()
        for link in links:
            href = link.get("href", "")
            href_lower = href.lower()
            for kw in subpage_keywords:
                if kw in href_lower:
                    full_url = urljoin(final_url, href)
                    if full_url not in found_subpages and urlparse(full_url).netloc == urlparse(final_url).netloc:
                        found_subpages.add(full_url)
                        break

        # Fetch relevant subpages (limit to 5)
        for sub_url in list(found_subpages)[:5]:
            try:
                sub_html, sub_final = self.fetch_page(sub_url)
                if sub_html:
                    subpage_htmls[sub_url] = sub_html
            except Exception:
                pass

        all_html = html + " ".join(subpage_htmls.values())
        all_soup = BeautifulSoup(all_html, "lxml")

        # Run checks
        result.checks.extend(self._check_transparency(soup, all_soup, final_url, found_subpages, subpage_htmls))
        result.checks.extend(self._check_cookies(soup, html, final_url))
        result.checks.extend(self._check_csrd(soup, all_soup, final_url, found_subpages))
        result.checks.extend(self._check_eaa(soup, final_url))

        return result

    # ─── Module 1: Åpenhetsloven (Transparency Act) ───

    def _check_transparency(self, soup, all_soup, url, subpage_urls, subpage_htmls):
        checks = []

        # 1. Check for transparency report (Redegjørelse for aktsomhetsvurderinger)
        report_keywords = [
            "redegjørelse for aktsomhetsvurdering",
            "redegjørelse aktsomhetsvurdering",
            "åpenhetsloven",
            "aktsomhetsvurdering",
            "due diligence",
            "menneskerettigheter",
            "transparency act",
        ]

        report_found = False
        report_url = ""
        report_evidence = ""

        # Check page text and links
        page_text = all_soup.get_text(" ", strip=True).lower()
        for kw in report_keywords:
            if kw in page_text:
                report_found = True
                report_evidence = kw
                break

        # Check link hrefs and text
        for link in all_soup.find_all("a", href=True):
            link_text = link.get_text(strip=True).lower()
            href = link.get("href", "").lower()
            for kw in report_keywords:
                if kw in link_text or kw in href:
                    report_found = True
                    report_url = urljoin(url, link.get("href", ""))
                    report_evidence = f"Link: {link.get_text(strip=True)}"
                    break

        checks.append(ComplianceCheck(
            module="Åpenhetsloven",
            check_id="transparency_report",
            title="Transparency Report Available",
            title_no="Redegjørelse tilgjengelig",
            description="The 'Account of Due Diligence' (Redegjørelse for aktsomhetsvurderinger) must be easily found on the website.",
            passed=report_found,
            severity="critical",
            details=f"Found at: {report_url}" if report_url else ("Keywords found in page text" if report_found else "No transparency report or related keywords found"),
            evidence=report_evidence,
            legal_basis="Åpenhetsloven §5 - Plikt til å redegjøre for aktsomhetsvurderinger",
        ))

        # 2. Check if report is current year
        current_year = str(datetime.now().year)
        previous_year = str(datetime.now().year - 1)
        report_dated = False
        date_evidence = ""

        if report_found:
            # Look for year references near transparency keywords
            for kw in report_keywords:
                pattern = re.compile(
                    rf'(?:{re.escape(kw)})[\s\S]{{0,500}}(?:{current_year}|{previous_year})',
                    re.IGNORECASE
                )
                match = pattern.search(page_text)
                if match:
                    report_dated = True
                    date_evidence = f"Year reference found near '{kw}'"
                    break

                # Also check reverse: year then keyword
                pattern2 = re.compile(
                    rf'(?:{current_year}|{previous_year})[\s\S]{{0,500}}(?:{re.escape(kw)})',
                    re.IGNORECASE
                )
                match2 = pattern2.search(page_text)
                if match2:
                    report_dated = True
                    date_evidence = f"Year reference found near '{kw}'"
                    break

        checks.append(ComplianceCheck(
            module="Åpenhetsloven",
            check_id="transparency_report_current",
            title="Report Up-to-Date",
            title_no="Redegjørelse oppdatert",
            description=f"The report should be dated for {previous_year} or {current_year} (deadline June 30th annually).",
            passed=report_dated,
            severity="serious",
            details=date_evidence if report_dated else "Could not verify report date" + (" (no report found)" if not report_found else ""),
            evidence="",
            legal_basis="Åpenhetsloven §5 - Årlig redegjørelse",
        ))

        # 3. Contact point for questions
        contact_keywords = [
            "spør oss om åpenhetsloven",
            "åpenhetsloven kontakt",
            "rett til informasjon",
            "right to information",
            "innsynsforespørsel",
        ]

        # Also check for general contact info near transparency content
        contact_found = False
        contact_evidence = ""

        for kw in contact_keywords:
            if kw in page_text:
                contact_found = True
                contact_evidence = f"Found: '{kw}'"
                break

        # Check for email links near transparency content
        if not contact_found and report_found:
            for link in all_soup.find_all("a", href=True):
                href = link.get("href", "")
                if href.startswith("mailto:"):
                    # Check if near transparency keywords
                    parent_text = ""
                    for parent in link.parents:
                        parent_text = parent.get_text(" ", strip=True).lower()
                        if len(parent_text) > 200:
                            break
                    for kw in report_keywords:
                        if kw in parent_text:
                            contact_found = True
                            contact_evidence = f"Email found near transparency content: {href}"
                            break
                    if contact_found:
                        break

        checks.append(ComplianceCheck(
            module="Åpenhetsloven",
            check_id="transparency_contact",
            title="Contact Point for Questions",
            title_no="Kontaktpunkt for spørsmål",
            description="There must be a clear way to ask questions about human rights due diligence (response required within 3 weeks).",
            passed=contact_found,
            severity="serious",
            details=contact_evidence if contact_found else "No specific contact point for transparency inquiries found",
            evidence="",
            legal_basis="Åpenhetsloven §6 - Rett til informasjon",
        ))

        return checks

    # ─── Module 2: Cookies / Ny Ekomlov & GDPR ───

    def _check_cookies(self, soup, html, url):
        checks = []
        html_lower = html.lower()

        # Detect cookie banner/consent elements
        cookie_selectors = [
            # Common cookie consent libraries
            {"id": re.compile(r"cookie", re.I)},
            {"class": re.compile(r"cookie", re.I)},
            {"id": re.compile(r"consent", re.I)},
            {"class": re.compile(r"consent", re.I)},
            {"id": re.compile(r"gdpr", re.I)},
            {"class": re.compile(r"gdpr", re.I)},
            {"id": re.compile(r"informasjonskaps", re.I)},
            {"class": re.compile(r"informasjonskaps", re.I)},
            {"id": re.compile(r"CybotCookiebot", re.I)},
            {"id": re.compile(r"onetrust", re.I)},
            {"class": re.compile(r"onetrust", re.I)},
        ]

        cookie_elements = []
        for sel in cookie_selectors:
            found = soup.find_all(attrs=sel)
            cookie_elements.extend(found)

        has_cookie_banner = len(cookie_elements) > 0

        # Also check for Cookiebot, OneTrust, etc. in scripts
        cookie_scripts = [
            "cookiebot", "onetrust", "cookieconsent", "cookie-consent",
            "cookie-notice", "gdpr-cookie", "tarteaucitron",
            "complianz", "cookie-law", "iubenda",
        ]
        for script_kw in cookie_scripts:
            if script_kw in html_lower:
                has_cookie_banner = True
                break

        cookie_text = " ".join(el.get_text(" ", strip=True).lower() for el in cookie_elements)
        all_buttons = []
        for el in cookie_elements:
            all_buttons.extend(el.find_all(["button", "a", "input"]))

        button_texts = [b.get_text(strip=True).lower() for b in all_buttons]

        # 1. Reject button
        reject_keywords = [
            "avvis", "avslå", "reject", "deny", "nei takk",
            "bare nødvendige", "only necessary", "kun nødvendige",
            "decline", "refuse", "ikke godta",
        ]
        has_reject = False
        reject_evidence = ""
        for btn_text in button_texts:
            for kw in reject_keywords:
                if kw in btn_text:
                    has_reject = True
                    reject_evidence = f"Button: '{btn_text}'"
                    break
            if has_reject:
                break

        # Also check in cookie text for reject links
        if not has_reject:
            for kw in reject_keywords:
                if kw in cookie_text:
                    has_reject = True
                    reject_evidence = f"Found '{kw}' in cookie banner"
                    break

        checks.append(ComplianceCheck(
            module="Cookies / Ekomlov",
            check_id="cookie_reject_button",
            title="Reject All Button",
            title_no="Avvis alle-knapp",
            description="Cookie banner must have a clear 'Reject All' button on the first layer, equally prominent as 'Accept'.",
            passed=has_reject,
            severity="critical",
            details=reject_evidence if has_reject else ("Cookie banner found but no reject button" if has_cookie_banner else "No cookie banner detected"),
            evidence="",
            legal_basis="Ny Ekomlov §3-5 (2025), GDPR Art. 7",
        ))

        # 2. No pre-ticked boxes
        pre_ticked = False
        pretick_evidence = ""

        for el in cookie_elements:
            checkboxes = el.find_all("input", {"type": "checkbox"})
            for cb in checkboxes:
                if cb.has_attr("checked"):
                    label = ""
                    cb_id = cb.get("id", "")
                    if cb_id:
                        label_el = el.find("label", {"for": cb_id})
                        if label_el:
                            label = label_el.get_text(strip=True)
                    label_lower = (label or cb.get("name", "")).lower()
                    # Necessary cookies can be pre-ticked
                    necessary_kw = ["nødvendig", "necessary", "essential", "required", "påkrevd", "strengt"]
                    is_necessary = any(kw in label_lower for kw in necessary_kw)
                    if not is_necessary:
                        pre_ticked = True
                        pretick_evidence = f"Pre-ticked: '{label or cb.get('name', 'unknown')}'"
                        break

        checks.append(ComplianceCheck(
            module="Cookies / Ekomlov",
            check_id="cookie_no_preticks",
            title="No Pre-ticked Boxes",
            title_no="Ingen forhåndsavkryssede bokser",
            description="No cookie category boxes should be pre-ticked except 'Necessary/Nødvendige'.",
            passed=not pre_ticked,
            severity="critical",
            details=pretick_evidence if pre_ticked else "No illegal pre-ticked boxes found" + ("" if has_cookie_banner else " (no cookie banner detected)"),
            evidence="",
            legal_basis="GDPR Art. 4(11), Art. 7 - Active consent required",
        ))

        # 3. Granular choice
        has_granular = False
        granular_evidence = ""

        category_keywords = [
            "statistikk", "statistics", "analytics",
            "markedsføring", "marketing", "advertising",
            "funksjonelle", "functional", "preferences",
            "personalisering",
        ]

        for el in cookie_elements:
            el_text = el.get_text(" ", strip=True).lower()
            found_categories = [kw for kw in category_keywords if kw in el_text]
            if len(found_categories) >= 2:
                has_granular = True
                granular_evidence = f"Categories found: {', '.join(found_categories)}"
                break

        # Also check for cookie settings/preferences link
        if not has_granular:
            settings_kw = ["innstillinger", "settings", "preferences", "tilpass", "customize", "manage"]
            for btn_text in button_texts:
                for kw in settings_kw:
                    if kw in btn_text:
                        has_granular = True
                        granular_evidence = f"Settings button: '{btn_text}'"
                        break
                if has_granular:
                    break

        checks.append(ComplianceCheck(
            module="Cookies / Ekomlov",
            check_id="cookie_granular",
            title="Granular Cookie Choices",
            title_no="Detaljert cookievalg",
            description="Users must be able to choose specific cookie categories (Marketing, Statistics) separately.",
            passed=has_granular,
            severity="serious",
            details=granular_evidence if has_granular else ("Cookie banner found but no granular choices" if has_cookie_banner else "No cookie banner detected"),
            evidence="",
            legal_basis="GDPR Art. 7, Ny Ekomlov §3-5",
        ))

        # 4. Privacy policy in Norwegian
        privacy_links = []
        privacy_keywords = ["personvern", "privacy", "informasjonskapsler", "cookies"]
        for link in soup.find_all("a", href=True):
            link_text = link.get_text(strip=True).lower()
            href = link.get("href", "").lower()
            for kw in privacy_keywords:
                if kw in link_text or kw in href:
                    privacy_links.append(link)
                    break

        has_privacy_no = False
        privacy_evidence = ""
        for link in privacy_links:
            link_text = link.get_text(strip=True).lower()
            if any(no_kw in link_text for no_kw in ["personvern", "informasjonskapsler"]):
                has_privacy_no = True
                privacy_evidence = f"Norwegian privacy link: '{link.get_text(strip=True)}'"
                break

        if not has_privacy_no:
            # Check if any privacy page exists (even in English)
            if privacy_links:
                has_privacy_no = False
                privacy_evidence = f"Privacy link found but may not be in Norwegian: '{privacy_links[0].get_text(strip=True)}'"

        checks.append(ComplianceCheck(
            module="Cookies / Ekomlov",
            check_id="privacy_norwegian",
            title="Privacy Policy in Norwegian",
            title_no="Personvernerklæring på norsk",
            description="Privacy policy must be available in Norwegian for sites targeting Norwegian users.",
            passed=has_privacy_no,
            severity="serious",
            details=privacy_evidence if privacy_evidence else "No privacy policy link found",
            evidence="",
            legal_basis="GDPR Art. 12 - Transparent information in clear language",
        ))

        # 5. Data transfer check (US tools)
        us_tools = [
            ("Google Analytics", ["google-analytics", "googletagmanager", "gtag", "ga.js", "analytics.js"]),
            ("Google Ads", ["googleads", "googlesyndication", "doubleclick"]),
            ("Facebook Pixel", ["facebook.net/en_US/fbevents", "connect.facebook"]),
            ("HubSpot", ["hubspot", "hs-scripts", "hs-analytics"]),
            ("Hotjar", ["hotjar"]),
            ("Intercom", ["intercom"]),
            ("Mailchimp", ["mailchimp"]),
        ]

        found_us_tools = []
        for tool_name, patterns in us_tools:
            for pat in patterns:
                if pat in html_lower:
                    found_us_tools.append(tool_name)
                    break

        # Check for transfer safeguards mentions
        safeguard_keywords = [
            "schrems", "standard contractual clauses", "scc",
            "adequacy decision", "overføringsgrunnlag",
            "tredjeland", "dataoverføring", "data transfer",
            "standardavtale", "binding corporate rules",
        ]
        page_text = soup.get_text(" ", strip=True).lower()
        has_safeguard_mention = any(kw in page_text for kw in safeguard_keywords)

        if found_us_tools:
            checks.append(ComplianceCheck(
                module="Cookies / Ekomlov",
                check_id="data_transfer",
                title="US Data Transfer Safeguards",
                title_no="Overføringsgrunnlag USA",
                description="If using US tools, data transfer safeguards must be documented (Schrems II).",
                passed=has_safeguard_mention,
                severity="moderate",
                details=f"US tools detected: {', '.join(set(found_us_tools))}. {'Transfer safeguards mentioned.' if has_safeguard_mention else 'No mention of transfer safeguards found.'}",
                evidence="",
                legal_basis="GDPR Chapter V, Schrems II (C-311/18)",
            ))

        return checks

    # ─── Module 3: CSRD Sustainability Reporting ───

    def _check_csrd(self, soup, all_soup, url, subpage_urls):
        checks = []
        page_text = all_soup.get_text(" ", strip=True).lower()

        # 1. Sustainability reporting presence
        sustainability_keywords = [
            "bærekraft", "sustainability", "csrd",
            "bærekraftsrapport", "sustainability report",
            "esg", "klimaregnskap", "climate accounts",
            "miljørapport", "environmental report",
            "samfunnsansvar", "corporate responsibility",
        ]

        found_keywords = [kw for kw in sustainability_keywords if kw in page_text]
        has_sustainability = len(found_keywords) > 0

        # Check for links to sustainability pages/PDFs
        sustainability_links = []
        for link in all_soup.find_all("a", href=True):
            link_text = link.get_text(strip=True).lower()
            href = link.get("href", "").lower()
            for kw in sustainability_keywords:
                if kw in link_text or kw in href:
                    sustainability_links.append({
                        "text": link.get_text(strip=True),
                        "url": urljoin(url, link.get("href", "")),
                    })
                    break

        checks.append(ComplianceCheck(
            module="CSRD / Bærekraft",
            check_id="sustainability_reporting",
            title="Sustainability Reporting",
            title_no="Bærekraftsrapportering",
            description="Sustainability data should be available, ideally integrated into the annual report.",
            passed=has_sustainability,
            severity="moderate",
            details=f"Keywords found: {', '.join(found_keywords[:5])}" if found_keywords else "No sustainability/ESG content found",
            evidence=f"Links: {', '.join(l['text'] for l in sustainability_links[:3])}" if sustainability_links else "",
            legal_basis="CSRD (EU 2022/2464) - Krav til bærekraftsrapportering",
        ))

        # 2. Check for annual report / årsrapport
        annual_report_kw = [
            "årsrapport", "årsmelding", "annual report",
            "årsberetning", "styrets beretning",
        ]
        has_annual_report = any(kw in page_text for kw in annual_report_kw)
        annual_links = []
        for link in all_soup.find_all("a", href=True):
            link_text = link.get_text(strip=True).lower()
            href = link.get("href", "").lower()
            for kw in annual_report_kw:
                if kw in link_text or kw in href:
                    annual_links.append(link.get_text(strip=True))
                    break

        if has_sustainability and has_annual_report:
            integration_note = "Both sustainability and annual report content found. Manual verification recommended to confirm integration."
        elif has_sustainability:
            integration_note = "Sustainability content found but no annual report reference. May be separate."
        else:
            integration_note = "No sustainability or annual report content detected."

        checks.append(ComplianceCheck(
            module="CSRD / Bærekraft",
            check_id="sustainability_integrated",
            title="Integrated in Annual Report",
            title_no="Integrert i årsrapport",
            description="CSRD requires sustainability data to be in the board of directors' report, not just a separate brochure.",
            passed=has_sustainability and has_annual_report,
            severity="moderate",
            details=integration_note,
            evidence=f"Annual report links: {', '.join(annual_links[:3])}" if annual_links else "",
            legal_basis="CSRD Art. 19a - Sustainability in management report",
        ))

        return checks

    # ─── Module 4: European Accessibility Act (EAA) ───

    def _check_eaa(self, soup, url):
        checks = []

        # 1. Feedback mechanism for accessibility
        feedback_keywords = [
            "tilgjengelighet", "accessibility",
            "universell utforming", "uu-tilbakemelding",
            "meld fra om tilgjengelighet", "report accessibility",
            "tilgjengelighetserklæring",
        ]

        feedback_found = False
        feedback_evidence = ""

        page_text = soup.get_text(" ", strip=True).lower()

        # Check for accessibility feedback links/forms
        for link in soup.find_all("a", href=True):
            link_text = link.get_text(strip=True).lower()
            href = link.get("href", "").lower()
            for kw in feedback_keywords:
                if kw in link_text or kw in href:
                    feedback_found = True
                    feedback_evidence = f"Link: '{link.get_text(strip=True)}' -> {urljoin(url, link.get('href', ''))}"
                    break
            if feedback_found:
                break

        # Also check for uustatus.no links
        if not feedback_found:
            for link in soup.find_all("a", href=True):
                if "uustatus.no" in link.get("href", ""):
                    feedback_found = True
                    feedback_evidence = f"UUstatus link found: {link.get('href', '')}"
                    break

        checks.append(ComplianceCheck(
            module="EAA / Tilgjengelighet",
            check_id="eaa_feedback",
            title="Accessibility Feedback Mechanism",
            title_no="Tilbakemeldingsmekanisme for tilgjengelighet",
            description="Users must be able to report accessibility barriers (required by EAA from June 2025).",
            passed=feedback_found,
            severity="serious",
            details=feedback_evidence if feedback_found else "No accessibility feedback mechanism found",
            evidence="",
            legal_basis="European Accessibility Act (EU 2019/882) Art. 9",
        ))


        return checks

    def cleanup(self):
        """Clean up resources."""
        if self.use_browser and BROWSER_AVAILABLE:
            try:
                close_browser()
            except Exception:
                pass


def generate_compliance_html(result, output_file=None):
    """Generate an HTML report from compliance results."""
    summary = result.summary
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Group checks by module
    modules = {}
    for check in result.checks:
        if check.module not in modules:
            modules[check.module] = []
        modules[check.module].append(check)

    score_color = "#4caf50" if summary["score_pct"] >= 80 else ("#ff9800" if summary["score_pct"] >= 50 else "#f44336")

    html = f"""<!DOCTYPE html>
<html lang="no">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Compliance Audit: {result.url}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; }}
  .container {{ max-width: 960px; margin: 0 auto; padding: 20px; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 5px; color: #1a237e; }}
  .subtitle {{ color: #666; font-size: 0.9rem; margin-bottom: 20px; }}
  .score-card {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 24px; }}
  .score-circle {{ width: 80px; height: 80px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; font-weight: bold; color: white; background: {score_color}; flex-shrink: 0; }}
  .score-details {{ flex: 1; }}
  .score-details h2 {{ font-size: 1.1rem; margin-bottom: 4px; }}
  .score-bar {{ display: flex; gap: 8px; margin-top: 8px; }}
  .score-bar .passed {{ background: #e8f5e9; color: #2e7d32; padding: 4px 10px; border-radius: 12px; font-size: 0.85rem; }}
  .score-bar .failed {{ background: #ffebee; color: #c62828; padding: 4px 10px; border-radius: 12px; font-size: 0.85rem; }}
  .module {{ background: white; border-radius: 12px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); overflow: hidden; }}
  .module-header {{ padding: 16px 20px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }}
  .module-header h3 {{ font-size: 1rem; color: #1a237e; }}
  .module-score {{ font-size: 0.85rem; padding: 3px 10px; border-radius: 10px; font-weight: 600; }}
  .module-score.good {{ background: #e8f5e9; color: #2e7d32; }}
  .module-score.warn {{ background: #fff3e0; color: #e65100; }}
  .module-score.bad {{ background: #ffebee; color: #c62828; }}
  .check {{ padding: 14px 20px; border-bottom: 1px solid #f0f0f0; }}
  .check:last-child {{ border-bottom: none; }}
  .check-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }}
  .check-icon {{ font-size: 1.1rem; }}
  .check-title {{ font-weight: 600; font-size: 0.95rem; }}
  .check-desc {{ font-size: 0.85rem; color: #666; margin-bottom: 4px; }}
  .check-details {{ font-size: 0.85rem; color: #444; background: #f8f9fa; padding: 6px 10px; border-radius: 6px; margin-top: 6px; }}
  .check-legal {{ font-size: 0.8rem; color: #888; margin-top: 4px; font-style: italic; }}
  .severity {{ font-size: 0.75rem; padding: 2px 6px; border-radius: 4px; font-weight: 600; }}
  .severity.critical {{ background: #ffebee; color: #c62828; }}
  .severity.serious {{ background: #fff3e0; color: #e65100; }}
  .severity.moderate {{ background: #e3f2fd; color: #1565c0; }}
  .severity.info {{ background: #f3e5f5; color: #6a1b9a; }}
  .footer {{ text-align: center; color: #999; font-size: 0.8rem; margin-top: 24px; padding: 16px; }}
</style>
</head>
<body>
<div class="container">
  <h1>Compliance Audit</h1>
  <p class="subtitle">{result.url} &mdash; {timestamp}</p>

  <div class="score-card">
    <div class="score-circle">{summary['score_pct']}%</div>
    <div class="score-details">
      <h2>Samlet samsvarsscore</h2>
      <p style="font-size:0.9rem;color:#666;">Totalt {summary['total_checks']} sjekker gjennomført</p>
      <div class="score-bar">
        <span class="passed">Bestått: {summary['passed']}</span>
        <span class="failed">Ikke bestått: {summary['failed']}</span>
      </div>
    </div>
  </div>
"""

    for module_name, module_checks in modules.items():
        mod_passed = sum(1 for c in module_checks if c.passed)
        mod_total = len(module_checks)
        mod_pct = round(mod_passed / mod_total * 100) if mod_total else 0
        score_class = "good" if mod_pct >= 80 else ("warn" if mod_pct >= 50 else "bad")

        html += f"""
  <div class="module">
    <div class="module-header">
      <h3>{module_name}</h3>
      <span class="module-score {score_class}">{mod_passed}/{mod_total} bestått</span>
    </div>
"""
        for check in module_checks:
            icon = "&#x2705;" if check.passed else "&#x274C;"
            html += f"""
    <div class="check">
      <div class="check-header">
        <span class="check-icon">{icon}</span>
        <span class="check-title">{check.title_no}</span>
        <span class="severity {check.severity}">{check.severity}</span>
      </div>
      <div class="check-desc">{check.description}</div>
      <div class="check-details">{check.details}</div>
      <div class="check-legal">{check.legal_basis}</div>
    </div>
"""
        html += "  </div>\n"

    html += f"""
  <div class="footer">
    <p>Generert av ComplianceChecker &mdash; {timestamp}</p>
    <p>Moduler: Åpenhetsloven, Cookies/Ekomlov, CSRD, EAA</p>
  </div>
</div>
</body>
</html>"""

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Report saved to: {output_file}")

    return html


def main():
    parser = argparse.ArgumentParser(description="Norwegian Legal Compliance Checker")
    parser.add_argument("url", help="Website URL to audit")
    parser.add_argument("--no-browser", action="store_true", help="Disable browser-based fetching")
    parser.add_argument("--format", choices=["html", "json", "text"], default="html", help="Output format")
    parser.add_argument("--output", type=str, help="Output file path")
    parser.add_argument("--wait-for", type=str, default="load", help="Browser wait strategy")
    args = parser.parse_args()

    url = args.url
    if not url.startswith("http"):
        url = "https://" + url

    checker = ComplianceChecker(
        use_browser=not args.no_browser,
        wait_for=args.wait_for,
    )

    try:
        result = checker.check_site(url)
        summary = result.summary

        if args.format == "json":
            output = json.dumps({
                "url": result.url,
                "timestamp": result.timestamp,
                "summary": summary,
                "checks": [asdict(c) for c in result.checks],
            }, indent=2, ensure_ascii=False)
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(output)
            else:
                print(output)

        elif args.format == "html":
            out_file = args.output or f"compliance_{urlparse(url).netloc}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            generate_compliance_html(result, out_file)

        else:
            # Text format
            print(f"\n{'='*60}")
            print(f"COMPLIANCE AUDIT: {result.url}")
            print(f"{'='*60}")
            print(f"Score: {summary['score_pct']}% ({summary['passed']}/{summary['total_checks']} passed)")
            print()
            for check in result.checks:
                status = "PASS" if check.passed else "FAIL"
                print(f"  [{status}] [{check.severity:8s}] {check.module}: {check.title_no}")
                if check.details:
                    print(f"         {check.details}")
                print()

    finally:
        checker.cleanup()


if __name__ == "__main__":
    main()
