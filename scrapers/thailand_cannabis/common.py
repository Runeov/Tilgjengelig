"""Shared utilities for Thailand cannabis market scrapers."""

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (compatible; ThaiCannabisMarketResearch/0.1; "
    "+contact via repo owner) Python-requests"
)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)


@dataclass
class Dispensary:
    """Normalized dispensary record. Fields default to None when unknown."""
    source: str
    source_id: str
    name: str
    city: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    opening_hours: Optional[str] = None
    price_range: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    licensed: Optional[bool] = None
    detail_url: Optional[str] = None
    lastmod: Optional[str] = None


def fetch(url: str, delay: float = 0.0, timeout: int = 20) -> str:
    """GET a URL and return text. delay is seconds to sleep *before* the request."""
    if delay > 0:
        time.sleep(delay)
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def iter_sitemap_urls(sitemap_xml: str) -> Iterator[dict]:
    """Yield {loc, lastmod} dicts from a sitemap.xml string. Handles default namespace."""
    root = ET.fromstring(sitemap_xml)
    # Strip namespace for simpler access
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"
    for url in root.findall(f"{ns}url"):
        loc_el = url.find(f"{ns}loc")
        if loc_el is None or not loc_el.text:
            continue
        lastmod_el = url.find(f"{ns}lastmod")
        yield {
            "loc": loc_el.text.strip(),
            "lastmod": lastmod_el.text.strip() if lastmod_el is not None and lastmod_el.text else None,
        }


def extract_jsonld(html: str) -> list[dict]:
    """Extract all parsed JSON-LD blocks from HTML."""
    soup = BeautifulSoup(html, "lxml")
    blocks: list[dict] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        text = tag.string or tag.get_text() or ""
        if not text.strip():
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            blocks.extend(d for d in data if isinstance(d, dict))
        elif isinstance(data, dict):
            blocks.append(data)
    return blocks


def find_jsonld_by_type(blocks: list[dict], wanted_types: set[str]) -> Optional[dict]:
    """Return the first JSON-LD block whose @type matches one of wanted_types."""
    for block in blocks:
        t = block.get("@type")
        if isinstance(t, list):
            if any(x in wanted_types for x in t):
                return block
        elif isinstance(t, str) and t in wanted_types:
            return block
    return None


_NAME_NOISE = re.compile(
    r"\b(cannabis|dispensary|weed|shop|store|bangkok|phuket|chiang\s*mai|pattaya|"
    r"koh\s*samui|thailand|th|club|lounge|cafe|coffee|bar|premium|the|and|&)\b",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_name(name: str) -> str:
    """Normalize a dispensary name for fuzzy matching across sources.

    Lowercases, strips common cannabis/location noise words, collapses non-alphanumerics.
    """
    if not name:
        return ""
    s = name.lower()
    # URL-decode in case input is a URL slug
    s = unquote(s)
    s = _NAME_NOISE.sub(" ", s)
    s = _NON_ALNUM.sub(" ", s)
    return " ".join(s.split())


def normalize_city(city: Optional[str]) -> str:
    """Normalize a city name for matching."""
    if not city:
        return ""
    s = city.lower().strip()
    # Common variants
    s = s.replace("chang wat ", "").replace("changwat ", "")
    s = _NON_ALNUM.sub(" ", s)
    return " ".join(s.split())


def write_csv(path: str, rows: list[dict], fieldnames: list[str]) -> None:
    """Write a list of dicts to CSV. Lists are joined with '; '."""
    import csv

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = {}
            for k in fieldnames:
                v = row.get(k)
                if isinstance(v, list):
                    out[k] = "; ".join(str(x) for x in v)
                elif v is None:
                    out[k] = ""
                else:
                    out[k] = v
            writer.writerow(out)


def dispensary_to_row(d: Dispensary) -> dict:
    """Convert a Dispensary dataclass to a dict for CSV output."""
    from dataclasses import asdict
    return asdict(d)


DISPENSARY_FIELDS = [
    "source", "source_id", "name", "city", "address",
    "latitude", "longitude", "phone", "website",
    "rating", "review_count", "opening_hours", "price_range",
    "tags", "licensed", "detail_url", "lastmod",
]
