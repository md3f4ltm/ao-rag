import re
import unicodedata
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
        if normalized in aliases or any(
            re.search(rf"\b{re.escape(alias)}\b", normalized)
            for alias in aliases
        ):
            return {"local": canonical, **location}

    return {"local": value, "place_terms": [value]}
