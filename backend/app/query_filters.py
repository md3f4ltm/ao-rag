import re
import unicodedata
import datetime
from typing import Any


KNOWN_LOCATIONS = {
    "lisboa": {
        "aliases": ["lisboa", "lisbon"],
        "place_terms": ["lisboa", "lisbon", "portugal"],
        "latitude": 38.7223,
        "longitude": -9.1393,
        "radius_km": 120,
    },
    "porto": {
        "aliases": ["porto", "oporto"],
        "place_terms": ["porto", "oporto", "portugal"],
        "latitude": 41.1579,
        "longitude": -8.6291,
        "radius_km": 120,
    },
    "acores": {
        "aliases": ["acores", "açores", "azores"],
        "place_terms": ["açores", "acores", "azores", "portugal"],
        "latitude": 37.7412,
        "longitude": -25.6756,
        "radius_km": 450,
    },
    "madeira": {
        "aliases": ["madeira"],
        "place_terms": ["madeira", "portugal"],
        "latitude": 32.7607,
        "longitude": -16.9595,
        "radius_km": 220,
    },
    "portugal": {
        "aliases": ["portugal"],
        "place_terms": ["portugal", "azores islands region"],
        "min_latitude": 30.0,
        "max_latitude": 43.0,
        "min_longitude": -32.0,
        "max_longitude": -6.0,
    },
}


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return ascii_text.lower().strip()


def resolve_location(value: str | None) -> dict[str, Any]:
    if not value:
        return {}

    normalized = normalize_text(value)
    for canonical, location in KNOWN_LOCATIONS.items():
        aliases = [normalize_text(alias) for alias in location["aliases"]]
        if normalized in aliases:
            return {"local": canonical, **location}

    return {"local": value, "place_terms": [value]}


def infer_filters_from_text(query: str) -> dict[str, Any]:
    text = normalize_text(query)
    filters: dict[str, Any] = {}

    latest_terms = ["ultimo", "último", "mais recente", "mais recentes", "recent", "latest"]
    if any(term in text for term in latest_terms):
        filters["sort"] = "latest"
        limit_match = re.search(
            r"\b(\d{1,3})\s+(?:sismos|terremotos|earthquakes)?\s*(?:mais\s+recentes|recentes|latest)",
            text,
        ) or re.search(
            r"(?:os\s+|as\s+)?(\d{1,3})\s+(?:ultimos|últimos|last)\s+(?:sismos|terremotos|earthquakes)",
            text,
        ) or re.search(
            r"(?:ultimos|últimos|last)\s+(\d{1,3})\s+(?:sismos|terremotos|earthquakes)",
            text,
        )
        if limit_match:
            filters["limit"] = min(int(limit_match.group(1)), 100)
        else:
            filters.setdefault("dias_atras", 30)

    for location in KNOWN_LOCATIONS.values():
        for alias in location["aliases"]:
            if re.search(rf"\b{re.escape(normalize_text(alias))}\b", text):
                filters.update(resolve_location(alias))
                break

    mag_match = re.search(r"(?:magnitude|mag)\s*(?:acima|superior|maior|>=|>)?\s*(\d+(?:[.,]\d+)?)", text)
    if mag_match and any(term in text for term in ["acima", "superior", "maior", ">", ">="]):
        filters["magnitude_min"] = float(mag_match.group(1).replace(",", "."))

    days_match = re.search(r"(?:ultimos|últimos|last)\s+(\d+)\s+(?:dias|days)", text)
    if days_match:
        filters["dias_atras"] = int(days_match.group(1))
    elif any(term in text for term in ["hoje", "today"]):
        filters["dias_atras"] = 1

    years_match = re.search(r"(?:ultimos|últimos|last)\s+(\d+)\s+(?:anos|years)", text)
    if years_match:
        years = int(years_match.group(1))
        today = datetime.date.today()
        filters["data_inicio"] = today.replace(year=today.year - years).isoformat()
        filters["data_fim"] = today.isoformat()

    since_match = re.search(r"(?:desde|since|from)\s+(20\d{2}|19\d{2})", text)
    if since_match:
        year = int(since_match.group(1))
        filters["data_inicio"] = f"{year}-01-01"
        filters["data_fim"] = datetime.date.today().isoformat()

    year_match = re.search(r"(?:em|in|ano)\s+(20\d{2}|19\d{2})", text)
    if year_match and "data_inicio" not in filters:
        year = int(year_match.group(1))
        filters["data_inicio"] = f"{year}-01-01"
        filters["data_fim"] = f"{year}-12-31"

    return filters


def merge_filters(llm_filters: dict[str, Any], query: str) -> dict[str, Any]:
    inferred = infer_filters_from_text(query)
    merged = {**inferred, **llm_filters}

    if inferred.get("limit") and inferred.get("sort") == "latest":
        merged["limit"] = inferred["limit"]
        merged["sort"] = "latest"
        merged.pop("dias_atras", None)

    if "local" in merged:
        location = resolve_location(str(merged["local"]))
        merged = {**merged, **location}

    return merged
