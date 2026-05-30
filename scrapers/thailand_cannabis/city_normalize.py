"""Normalize the messy `city` values from weed.th into canonical Thai province names.

weed.th's city column has these data-quality issues:
  - Thai-script duplicates (กระบี่ vs Krabi)
  - "Chang Wat <X>" prefix (Thai 'จังหวัด' = 'province') instead of just <X>
  - Spelling typos (Buogkan, Loburi)
  - Truncations (Nga instead of Phang Nga)
  - "N A" / empty for shops with no city

This module exposes `canonical_city(s)` which collapses all variants to a
single Royal-Thai-General-System (RTGS) province name. After normalization,
the 107 raw city values reduce to ~77 actual Thai provinces + 1 "(unknown)"
bucket.

Use `canonical_city(s)` everywhere you aggregate or filter by city.
"""

# Explicit aliases: dirty variant -> canonical RTGS name.
# Generic "Chang Wat <X>" stripping is handled separately in the function below.
CITY_ALIASES: dict[str, str] = {
    # Thai-script variants seen in the country scrape
    "สุราษฎร์ธานี": "Surat Thani",
    "กระบี่": "Krabi",
    "ภูเก็ต": "Phuket",
    "กรุงเทพมหานคร": "Bangkok",
    "สมุทรปราการ": "Samut Prakan",
    "หนองบัวลำภู": "Nong Bua Lam Phu",
    "ยโสธร": "Yasothon",
    "พังงา": "Phang Nga",

    # Spelling / spacing fixes
    "Phangnga": "Phang Nga",      # weed.th uses no-space; RTGS standard has a space
    "Loburi": "Lop Buri",          # typo
    "Buogkan": "Bueng Kan",        # typo
    "Nga": "Phang Nga",            # truncated

    # Empty / unknown
    "N A": "(unknown)",
    "": "(unknown)",
}


def canonical_city(s: str | None) -> str:
    """Return the canonical province name for a raw city value.

    Examples:
      canonical_city("Krabi")               -> "Krabi"
      canonical_city("Chang Wat Krabi")     -> "Krabi"
      canonical_city("Phangnga")            -> "Phang Nga"
      canonical_city("กระบี่")              -> "Krabi"
      canonical_city("Loburi")              -> "Lop Buri"
      canonical_city("")                    -> "(unknown)"
      canonical_city(None)                  -> "(unknown)"
    """
    if s is None:
        return "(unknown)"
    s = s.strip()
    if s in CITY_ALIASES:
        return CITY_ALIASES[s]
    # Generic "Chang Wat <X>" handling — strip the prefix, then re-apply
    # explicit aliases on the remainder (so "Chang Wat Phang Nga" -> "Phang Nga").
    if s.startswith("Chang Wat "):
        rest = s[len("Chang Wat "):].strip()
        return CITY_ALIASES.get(rest, rest)
    return s
