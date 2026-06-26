import datetime
import math
import os
import sqlite3
from typing import Any

import httpx


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_FILE = os.getenv("EARTHQUAKE_DB_FILE", os.path.join(BASE_DIR, "earthquakes.sqlite3"))
USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_month.geojson"
USGS_QUERY_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
CACHE_TTL_SECONDS = 10 * 60
MAX_HISTORY_DAYS = 3650


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS earthquakes (
                id TEXT PRIMARY KEY,
                place TEXT,
                magnitude REAL,
                time INTEGER,
                url TEXT,
                longitude REAL,
                latitude REAL,
                depth REAL,
                updated_at INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                trace TEXT,
                trace_duration REAL,
                filters TEXT,
                is_error INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_earthquakes_time ON earthquakes(time)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_earthquakes_magnitude ON earthquakes(magnitude)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)")


def save_session(session_id: str, title: str) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sessions (id, title, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                updated_at = CURRENT_TIMESTAMP
            """,
            (session_id, title),
        )


def save_message(
    session_id: str,
    role: str,
    content: str,
    trace: Any = None,
    trace_duration: float | None = None,
    filters: Any = None,
    is_error: bool = False,
) -> None:
    init_db()
    import json
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages (
                session_id, role, content, trace, trace_duration, filters, is_error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                json.dumps(trace) if trace else None,
                trace_duration,
                json.dumps(filters) if filters else None,
                1 if is_error else 0,
            ),
        )


def get_sessions() -> list[dict[str, Any]]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_session_messages(session_id: str) -> list[dict[str, Any]]:
    init_db()
    import json
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content, trace, trace_duration, filters, is_error
            FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,),
        ).fetchall()
    
    messages = []
    for row in rows:
        msg = dict(row)
        msg["trace"] = json.loads(msg["trace"]) if msg["trace"] else None
        msg["filters"] = json.loads(msg["filters"]) if msg["filters"] else None
        msg["is_error"] = bool(msg["is_error"])
        messages.append(msg)
    return messages


def delete_session(session_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def get_last_sync() -> datetime.datetime | None:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM sync_state WHERE key = 'last_sync'").fetchone()

    if not row:
        return None

    return datetime.datetime.fromisoformat(row["value"])


def sync_is_fresh() -> bool:
    last_sync = get_last_sync()
    if not last_sync:
        return False

    age = datetime.datetime.now(datetime.timezone.utc) - last_sync
    return age.total_seconds() < CACHE_TTL_SECONDS


async def refresh_earthquakes(force: bool = False) -> dict[str, Any]:
    init_db()

    if not force and sync_is_fresh():
        return {"updated": False, "reason": "cache_fresh", "count": count_earthquakes()}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(USGS_URL)
        response.raise_for_status()
        data = response.json()

    rows = save_features(data.get("features", []))

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sync_state(key, value)
            VALUES ('last_sync', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (datetime.datetime.now(datetime.timezone.utc).isoformat(),),
        )

    return {"updated": True, "reason": "synced_from_usgs", "count": len(rows)}


async def sync_history(filters: dict[str, Any], start_date: str, end_date: str) -> dict[str, Any]:
    init_db()
    start = parse_date(start_date)
    end = parse_date(end_date)
    today = datetime.datetime.now(datetime.timezone.utc).date()

    if end.date() > today:
        end = datetime.datetime.combine(today, datetime.time.min, tzinfo=datetime.timezone.utc)
    if start > end:
        start, end = end, start
    if (end - start).days > MAX_HISTORY_DAYS:
        start = end - datetime.timedelta(days=MAX_HISTORY_DAYS)

    requested_end_date = end.date().isoformat()
    api_end_date = (end + datetime.timedelta(days=1)).date().isoformat()
    orderby = "time"
    if filters.get("sort") in ["magnitude_desc", "impact"]:
        orderby = "magnitude"

    params: dict[str, Any] = {
        "format": "geojson",
        "starttime": start.date().isoformat(),
        "endtime": api_end_date,
        "orderby": orderby,
        "limit": min(int(filters.get("limit", 20000)), 20000),
    }

    if "magnitude_min" in filters:
        params["minmagnitude"] = filters["magnitude_min"]

    if all(key in filters for key in ["latitude", "longitude", "radius_km"]):
        params["latitude"] = filters["latitude"]
        params["longitude"] = filters["longitude"]
        params["maxradiuskm"] = filters["radius_km"]
    elif all(
        key in filters
        for key in ["min_latitude", "max_latitude", "min_longitude", "max_longitude"]
    ):
        params["minlatitude"] = filters["min_latitude"]
        params["maxlatitude"] = filters["max_latitude"]
        params["minlongitude"] = filters["min_longitude"]
        params["maxlongitude"] = filters["max_longitude"]

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(USGS_QUERY_URL, params=params)
        response.raise_for_status()
        data = response.json()

    rows = save_features(data.get("features", []))
    coverage_key = f"history:{params['starttime']}:{params['endtime']}:{filters.get('local', 'global')}"

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sync_state(key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (coverage_key, datetime.datetime.now(datetime.timezone.utc).isoformat()),
        )

    return {
        "updated": True,
        "reason": "history_synced_from_usgs",
        "count": len(rows),
        "start_date": params["starttime"],
        "end_date": requested_end_date,
        "geo_limited": "latitude" in params or "minlatitude" in params,
    }


def save_features(features: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    now_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    rows = []

    for feature in features:
        props = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []

        event_id = feature.get("id")
        if not event_id:
            continue

        rows.append(
            (
                event_id,
                props.get("place"),
                props.get("mag"),
                props.get("time"),
                props.get("url"),
                coords[0] if len(coords) > 0 else None,
                coords[1] if len(coords) > 1 else None,
                coords[2] if len(coords) > 2 else None,
                now_ms,
            )
        )

    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO earthquakes (
                id, place, magnitude, time, url, longitude, latitude, depth, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                place = excluded.place,
                magnitude = excluded.magnitude,
                time = excluded.time,
                url = excluded.url,
                longitude = excluded.longitude,
                latitude = excluded.latitude,
                depth = excluded.depth,
                updated_at = excluded.updated_at
            """,
            rows,
        )

    return rows


def count_earthquakes() -> int:
    init_db()
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM earthquakes").fetchone()
    return int(row["total"])


def search_earthquakes(filters: dict[str, Any]) -> list[dict[str, Any]]:
    init_db()
    clauses = []
    params: list[Any] = []
    has_geo_filter = all(key in filters for key in ["latitude", "longitude", "radius_km"])
    has_bbox_filter = all(
        key in filters
        for key in ["min_latitude", "max_latitude", "min_longitude", "max_longitude"]
    )

    place_terms = filters.get("place_terms") or ([filters["local"]] if filters.get("local") else [])
    if place_terms and not has_geo_filter and not has_bbox_filter:
        term_clauses = []
        for term in place_terms:
            term_clauses.append("LOWER(place) LIKE ?")
            params.append(f"%{str(term).lower()}%")
        clauses.append(f"({' OR '.join(term_clauses)})")

    if has_bbox_filter:
        clauses.append("latitude IS NOT NULL AND latitude BETWEEN ? AND ?")
        params.extend([filters["min_latitude"], filters["max_latitude"]])
        clauses.append("longitude IS NOT NULL AND longitude BETWEEN ? AND ?")
        params.extend([filters["min_longitude"], filters["max_longitude"]])

    if has_geo_filter:
        latitude = float(filters["latitude"])
        longitude = float(filters["longitude"])
        radius_km = float(filters["radius_km"])
        lat_delta = radius_km / 111.0
        lon_delta = radius_km / max(111.0 * math.cos(math.radians(latitude)), 1.0)
        clauses.append("latitude IS NOT NULL AND latitude BETWEEN ? AND ?")
        params.extend([latitude - lat_delta, latitude + lat_delta])
        clauses.append("longitude IS NOT NULL AND longitude BETWEEN ? AND ?")
        params.extend([longitude - lon_delta, longitude + lon_delta])

    if "magnitude_min" in filters:
        clauses.append("magnitude IS NOT NULL AND magnitude >= ?")
        params.append(filters["magnitude_min"])

    if "magnitude_max" in filters:
        clauses.append("magnitude IS NOT NULL AND magnitude <= ?")
        params.append(filters["magnitude_max"])

    if "dias_atras" in filters:
        try:
            dias_atras = int(filters["dias_atras"])
        except (ValueError, TypeError):
            dias_atras = 7

        cutoff_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            days=dias_atras
        )
        clauses.append("time IS NOT NULL AND time >= ?")
        params.append(int(cutoff_time.timestamp() * 1000))

    if "data_inicio" in filters:
        clauses.append("time IS NOT NULL AND time >= ?")
        params.append(date_to_ms(filters["data_inicio"]))

    if "data_fim" in filters:
        clauses.append("time IS NOT NULL AND time <= ?")
        params.append(date_to_ms(filters["data_fim"], end_of_day=True))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit = min(int(filters.get("limit", 500)), 500)
    order_by = "COALESCE(time, 0) DESC"
    if filters.get("sort") in ["magnitude_desc", "impact"]:
        order_by = "COALESCE(magnitude, -999) DESC, COALESCE(time, 0) DESC"

    query = f"""
        SELECT id, place, magnitude, time, url, longitude, latitude, depth
        FROM earthquakes
        {where}
        ORDER BY {order_by}
        LIMIT {limit}
    """

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    results = [dict(row) for row in rows]

    if has_geo_filter:
        latitude = float(filters["latitude"])
        longitude = float(filters["longitude"])
        radius_km = float(filters["radius_km"])
        nearby = []

        for row in results:
            if row["latitude"] is None or row["longitude"] is None:
                continue

            distance = haversine_km(latitude, longitude, row["latitude"], row["longitude"])
            if distance <= radius_km:
                row["distance_km"] = round(distance, 1)
                nearby.append(row)

        return nearby[:limit]

    return results[:limit]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_date(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value).replace(tzinfo=datetime.timezone.utc)


def date_to_ms(value: str, end_of_day: bool = False) -> int:
    parsed = parse_date(value)
    if end_of_day:
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999000)
    return int(parsed.timestamp() * 1000)
