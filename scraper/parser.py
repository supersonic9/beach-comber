import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

_ID_RE = re.compile(r"setLastSearch\('([^']+)'\)")
_BEDROOM_RE = re.compile(r"\bT(\d+)\b", re.IGNORECASE)
_SIZE_RE = re.compile(r"([\d.,]+)\s*m²", re.IGNORECASE)


def extract_listings(html: str) -> list[dict[str, Any]]:
    """Parse listings from a Casa Sapo search results page."""
    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, Any]] = []

    for card in soup.select("a.property-info"):
        parsed = _parse_card(card)
        if parsed:
            results.append(parsed)

    return results


def _parse_card(card: Any) -> dict[str, Any] | None:
    # ID from onclick attribute
    onclick = card.get("onclick", "")
    m = _ID_RE.search(onclick)
    if not m:
        return None
    listing_id = m.group(1)

    # Real URL extracted from redirect href (?l= param)
    href = card.get("href", "")
    url = _extract_real_url(href)

    # Price: "490.000 €" — PT thousands separator is "."
    price: int | None = None
    price_tag = card.select_one(".property-price-value")
    if price_tag:
        price = _parse_pt_price(price_tag.get_text(strip=True))

    # Features text: "Em construção  ·  90m²"
    size_sqm: float | None = None
    condition: str | None = None
    feat_tag = card.select_one(".property-features-text")
    if feat_tag:
        feat_text = feat_tag.get_text(strip=True)
        size_sqm, condition = _parse_features(feat_text)

    # Bedrooms: "Apartamento T0" → "T0"
    bedrooms: str | None = None
    type_tag = card.select_one(".property-type")
    if type_tag:
        type_text = type_tag.get_text(strip=True)
        bm = _BEDROOM_RE.search(type_text)
        if bm:
            bedrooms = f"T{bm.group(1)}"

    # Location
    location: str | None = None
    loc_tag = card.select_one(".property-location")
    if loc_tag:
        location = loc_tag.get_text(strip=True) or None

    price_per_sqm: float | None = None
    if price and size_sqm and size_sqm > 0:
        price_per_sqm = round(price / size_sqm, 2)

    return {
        "id": listing_id,
        "price": price,
        "price_per_sqm": price_per_sqm,
        "size_sqm": size_sqm,
        "bedrooms": bedrooms,
        "location": location,
        "condition": condition,
        "url": url,
    }


def _extract_real_url(href: str) -> str:
    """Extract canonical casa.sapo.pt URL from redirect href."""
    parsed = urlparse(href)
    qs = parse_qs(parsed.query)
    if "l" in qs:
        real = qs["l"][0]
        # Strip tracking params from the real URL
        real_parsed = urlparse(real)
        return real_parsed._replace(query="").geturl()
    return href


def _parse_pt_price(text: str) -> int | None:
    """Parse Portuguese price string: '490.000 €' → 490000."""
    m = re.search(r"([\d.]+)\s*€", text)
    if not m:
        return None
    cleaned = m.group(1).replace(".", "")
    return int(cleaned) if cleaned.isdigit() else None


def _parse_features(text: str) -> tuple[float | None, str | None]:
    """Parse 'Em construção  ·  90m²' → (90.0, 'Em construção')."""
    size_sqm: float | None = None
    condition: str | None = None

    parts = [p.strip() for p in text.split("·")]
    non_size_parts: list[str] = []
    for part in parts:
        m = _SIZE_RE.search(part)
        if m:
            size_sqm = _parse_float(m.group(1))
        elif part:
            non_size_parts.append(part)
    condition = non_size_parts[0] if non_size_parts else None

    return size_sqm, condition


def _parse_float(text: str) -> float | None:
    # PT format uses "." as thousands sep and "," as decimal
    cleaned = text.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None
