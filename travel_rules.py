"""
Travel Industry Compliance Rule Registry - Finnmark
Maps Norwegian travel law requirements to checkable criteria.

Legal bases:
  - Markedsføringsloven (Marketing Act) - price/contact transparency
  - Angrerettloven (Right of Withdrawal Act) - cancellation/refund info
  - Pakkereiseloven (Package Travel Act) - tour operator obligations
  - Personopplysningsloven / GDPR - privacy/cookie requirements
  - Enhetsregisterloven - org.nr display obligation
"""

TRAVEL_RULES = {
    # ─── Pricing transparency ─────────────────────────────────────────────────
    "price.1a": {
        "id": "price.1a",
        "name": "Priser oppgitt inkl. eller ekskl. mva",
        "name_en": "Prices stated with VAT status",
        "criterion": "price.1",
        "criterion_name": "Prisgjennomsiktighet",
        "criterion_name_en": "Price transparency",
        "level": "required",
        "impact": "serious",
        "test_object": "Priselementer på siden",
        "legal_basis": "Markedsføringsloven §7, Prisopplysningsforskriften §3",
        "auto": True,
    },
    "price.1b": {
        "id": "price.1b",
        "name": "Totalprisen er synlig før betaling",
        "name_en": "Total price visible before payment",
        "criterion": "price.1",
        "criterion_name": "Prisgjennomsiktighet",
        "criterion_name_en": "Price transparency",
        "level": "required",
        "impact": "critical",
        "test_object": "Bestillingsskjema / kassa",
        "legal_basis": "Pakkereiseloven §28, Angrerettloven §8",
        "auto": False,
    },
    "price.2a": {
        "id": "price.2a",
        "name": "Ingen skjulte gebyrer etter at pris er vist",
        "name_en": "No hidden fees after price shown",
        "criterion": "price.2",
        "criterion_name": "Gebyrklarhet",
        "criterion_name_en": "Fee clarity",
        "level": "recommended",
        "impact": "moderate",
        "test_object": "Bestillingsflyt",
        "legal_basis": "Markedsføringsloven §6",
        "auto": False,
    },

    # ─── Contact information ──────────────────────────────────────────────────
    "contact.1a": {
        "id": "contact.1a",
        "name": "Norsk telefonnummer er synlig på siden",
        "name_en": "Norwegian phone number visible on page",
        "criterion": "contact.1",
        "criterion_name": "Kontaktinformasjon",
        "criterion_name_en": "Contact information",
        "level": "required",
        "impact": "moderate",
        "test_object": "Header / Footer / Kontaktside",
        "legal_basis": "Markedsføringsloven §6, ehandelsloven §8",
        "auto": True,
    },
    "contact.1b": {
        "id": "contact.1b",
        "name": "E-postadresse eller kontaktskjema er tilgjengelig",
        "name_en": "Email address or contact form available",
        "criterion": "contact.1",
        "criterion_name": "Kontaktinformasjon",
        "criterion_name_en": "Contact information",
        "level": "required",
        "impact": "moderate",
        "test_object": "Kontaktseksjon",
        "legal_basis": "ehandelsloven §8",
        "auto": True,
    },
    "contact.1c": {
        "id": "contact.1c",
        "name": "Fysisk adresse er oppgitt",
        "name_en": "Physical address is stated",
        "criterion": "contact.1",
        "criterion_name": "Kontaktinformasjon",
        "criterion_name_en": "Contact information",
        "level": "recommended",
        "impact": "minor",
        "test_object": "Footer",
        "legal_basis": "ehandelsloven §8",
        "auto": True,
    },

    # ─── Cancellation & booking terms ─────────────────────────────────────────
    "policy.1a": {
        "id": "policy.1a",
        "name": "Avbestillingsvilkår er tilgjengelige på nettstedet",
        "name_en": "Cancellation policy accessible on site",
        "criterion": "policy.1",
        "criterion_name": "Avbestillingsvilkår",
        "criterion_name_en": "Cancellation policy",
        "level": "required",
        "impact": "serious",
        "test_object": "Footer / Bestillingsflyt / Vilkår-side",
        "legal_basis": "Angrerettloven §11, Pakkereiseloven §31",
        "auto": True,
    },
    "policy.1b": {
        "id": "policy.1b",
        "name": "14-dagers angrerett er nevnt (digitale/nettbaserte kjøp)",
        "name_en": "14-day right of withdrawal mentioned",
        "criterion": "policy.1",
        "criterion_name": "Avbestillingsvilkår",
        "criterion_name_en": "Cancellation policy",
        "level": "required",
        "impact": "serious",
        "test_object": "Vilkår og betingelser",
        "legal_basis": "Angrerettloven §22",
        "auto": True,
    },
    "policy.2a": {
        "id": "policy.2a",
        "name": "Generelle vilkår og betingelser er lenket til",
        "name_en": "General terms and conditions linked",
        "criterion": "policy.2",
        "criterion_name": "Vilkår og betingelser",
        "criterion_name_en": "Terms and conditions",
        "level": "required",
        "impact": "moderate",
        "test_object": "Footer",
        "legal_basis": "Avtaleloven",
        "auto": True,
    },

    # ─── Regulatory / company identity ────────────────────────────────────────
    "org.1a": {
        "id": "org.1a",
        "name": "Organisasjonsnummer (org.nr.) er synlig på siden",
        "name_en": "Organisation number visible on page",
        "criterion": "org.1",
        "criterion_name": "Regulatorisk identitet",
        "criterion_name_en": "Regulatory identity",
        "level": "required",
        "impact": "serious",
        "test_object": "Footer",
        "legal_basis": "Enhetsregisterloven §21, Markedsføringsloven §6",
        "auto": True,
    },
    "org.1b": {
        "id": "org.1b",
        "name": "Firmanavn stemmer overens med Brønnøysundregisteret",
        "name_en": "Company name matches Brønnøysund registry",
        "criterion": "org.1",
        "criterion_name": "Regulatorisk identitet",
        "criterion_name_en": "Regulatory identity",
        "level": "recommended",
        "impact": "minor",
        "test_object": "Header / Footer",
        "legal_basis": "Foretaksnavneloven",
        "auto": False,
    },
    "org.2a": {
        "id": "org.2a",
        "name": "Reisegaranti / godkjenning fra Reisegarantifondet er synlig (pakketurer)",
        "name_en": "Travel guarantee / Reisegarantifondet approval visible (package tours)",
        "criterion": "org.2",
        "criterion_name": "Reisegodkjenning",
        "criterion_name_en": "Travel operator approval",
        "level": "required",
        "impact": "critical",
        "test_object": "Footer / Om oss",
        "legal_basis": "Pakkereiseloven §55",
        "auto": True,
    },

    # ─── Privacy & GDPR ───────────────────────────────────────────────────────
    "gdpr.1a": {
        "id": "gdpr.1a",
        "name": "Personvernerklæring er lenket til",
        "name_en": "Privacy policy linked",
        "criterion": "gdpr.1",
        "criterion_name": "Personvern",
        "criterion_name_en": "Privacy",
        "level": "required",
        "impact": "serious",
        "test_object": "Footer",
        "legal_basis": "GDPR Art. 13, Personopplysningsloven §1",
        "auto": True,
    },
    "gdpr.1b": {
        "id": "gdpr.1b",
        "name": "Informasjonskapselbanner / samtykke er til stede",
        "name_en": "Cookie consent banner present",
        "criterion": "gdpr.1",
        "criterion_name": "Personvern",
        "criterion_name_en": "Privacy",
        "level": "required",
        "impact": "serious",
        "test_object": "Helsidesjekk ved første besøk",
        "legal_basis": "ekomloven §2-7b, GDPR Art. 6",
        "auto": True,
    },

    # ─── Language & content quality ───────────────────────────────────────────
    "content.1a": {
        "id": "content.1a",
        "name": "Nettstedet er tilgjengelig på norsk",
        "name_en": "Site available in Norwegian",
        "criterion": "content.1",
        "criterion_name": "Innholdskvalitet",
        "criterion_name_en": "Content quality",
        "level": "recommended",
        "impact": "moderate",
        "test_object": "Sidespråk",
        "legal_basis": "Språkloven §17",
        "auto": True,
    },
    "content.1b": {
        "id": "content.1b",
        "name": "Nettstedet er også tilgjengelig på engelsk",
        "name_en": "Site also available in English",
        "criterion": "content.1",
        "criterion_name": "Innholdskvalitet",
        "criterion_name_en": "Content quality",
        "level": "recommended",
        "impact": "minor",
        "test_object": "Språkvalg / hreflang",
        "legal_basis": "N/A – quality signal for tourism",
        "auto": True,
    },

    # ─── Booking experience ───────────────────────────────────────────────────
    "booking.1a": {
        "id": "booking.1a",
        "name": "Bestillingsknapp / CTA er synlig på forsiden",
        "name_en": "Booking CTA visible on homepage",
        "criterion": "booking.1",
        "criterion_name": "Bestillingsopplevelse",
        "criterion_name_en": "Booking experience",
        "level": "recommended",
        "impact": "moderate",
        "test_object": "Landingsside",
        "legal_basis": "N/A – quality signal",
        "auto": True,
    },
    "booking.1b": {
        "id": "booking.1b",
        "name": "Online bestilling er mulig (ikke kun telefon/e-post)",
        "name_en": "Online booking available (not phone/email only)",
        "criterion": "booking.1",
        "criterion_name": "Bestillingsopplevelse",
        "criterion_name_en": "Booking experience",
        "level": "recommended",
        "impact": "minor",
        "test_object": "Bestillingsflyt",
        "legal_basis": "N/A – quality signal",
        "auto": True,
    },
}


def get_rule(rule_id: str) -> dict:
    """Return a rule dict by ID, or an empty dict if not found."""
    return TRAVEL_RULES.get(rule_id, {})


def get_rules_by_criterion(criterion_id: str) -> list:
    """Return all rules for a given criterion ID."""
    return [r for r in TRAVEL_RULES.values() if r["criterion"] == criterion_id]


def get_required_rules() -> list:
    """Return all rules with level='required'."""
    return [r for r in TRAVEL_RULES.values() if r["level"] == "required"]
