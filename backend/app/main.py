from contextlib import asynccontextmanager
import asyncio
import json
import re
import time

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, Field
import httpx
from app.config import settings
from app.lmstudio import chat_with_tools, list_models, stream_chat, EARTHQUAKE_TOOLS
from app.earthquake_store import (
    count_earthquakes,
    get_last_sync,
    init_db,
    refresh_earthquakes,
    search_earthquakes,
    sync_history,
    save_session,
    save_message,
    get_sessions,
    get_session_messages,
    delete_session as db_delete_session,
)
from app.query_filters import KNOWN_LOCATIONS, resolve_location
from app.query_filters import normalize_text
from app.document_store import DOC_STORE

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        await refresh_earthquakes()
    except httpx.HTTPError as exc:
        print(f"USGS sync failed on startup: {exc}")
    yield


app = FastAPI(title="sismoGPT API", lifespan=lifespan)
frontend_dir = Path(__file__).resolve().parent.parent / "static"

class ChatHistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None
    model: str | None = None
    client_time: str | None = None
    timezone: str | None = None
    history: list[ChatHistoryMessage] = Field(default_factory=list)
    allowed_tools: list[str] | None = None


@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": get_sessions()}


@app.get("/api/sessions/{session_id}")
async def get_session_details(session_id: str):
    return {"messages": get_session_messages(session_id)}


@app.delete("/api/sessions/{session_id}")
async def delete_session_endpoint(session_id: str):
    db_delete_session(session_id)
    return {"status": "ok"}


@app.get("/api/health")
async def health():
    last_sync = get_last_sync()
    return {
        "status": "ok",
        "source": "USGS Earthquake Hazards Program",
        "database": "sqlite",
        "earthquakes_count": count_earthquakes(),
        "last_sync": last_sync.isoformat() if last_sync else None,
    }


@app.post("/api/sync")
async def sync():
    return await refresh_earthquakes(force=True)


@app.get("/api/models")
async def models():
    try:
        available_models = [model for model in await list_models() if "embedding" not in model.lower()]
        default_model = settings.LM_STUDIO_MODEL
        if default_model not in available_models and available_models:
            default_model = available_models[0]
        return {"models": available_models, "default_model": default_model}
    except httpx.HTTPError as exc:
        print(f"LM Studio model list failed: {exc}")
        return {"models": [settings.LM_STUDIO_MODEL], "default_model": settings.LM_STUDIO_MODEL}


async def publish_trace(trace: list[dict], started_at: float, emit=None) -> None:
    if not emit:
        return

    await emit({
        "event": "trace",
        "trace": trace,
        "trace_duration_seconds": round(time.perf_counter() - started_at, 2),
    })


def compact_earthquake(item: dict) -> dict:
    return {
        "place": item.get("place"),
        "magnitude": item.get("magnitude"),
        "time": item.get("time"),
        "time_utc": (
            datetime.datetime.fromtimestamp(item["time"] / 1000, tz=datetime.timezone.utc).isoformat()
            if item.get("time")
            else None
        ),
        "depth": item.get("depth"),
        "distance_km": item.get("distance_km"),
        "url": item.get("url"),
    }


def mentions_last_year(text: str) -> bool:
    normalized = normalize_text(text)
    return any(
        phrase in normalized
        for phrase in [
            "ultimo ano",
            "ultimos 12 meses",
            "12 meses",
            "last year",
            "past year",
        ]
    )


def is_high_impact_query(text: str) -> bool:
    normalized = normalize_text(text)
    return any(
        term in normalized
        for term in [
            "mais impactantes",
            "mais fortes",
            "maiores",
            "maior magnitude",
            "strongest",
            "largest",
            "most impactful",
        ]
    )


def recent_history_days(query: str, history: list[ChatHistoryMessage]) -> int | None:
    if mentions_last_year(query):
        return 365

    normalized = normalize_text(query)
    if any(term in normalized for term in ["acima de", "maior que", "mais de", "above"]):
        for item in reversed(history[-6:]):
            if mentions_last_year(item.content):
                return 365

    return None


def has_high_impact_context(query: str, history: list[ChatHistoryMessage]) -> bool:
    if is_high_impact_query(query):
        return True

    normalized = normalize_text(query)
    if any(term in normalized for term in ["acima de", "maior que", "mais de", "above"]):
        return any(is_high_impact_query(item.content) for item in history[-6:])

    return False


def is_earthquake_query(query: str) -> bool:
    normalized = normalize_text(query)
    return any(
        term in normalized
        for term in [
            "ismo",
            "ismos",
            "sismo",
            "sismos",
            "terramoto",
            "terramotos",
            "earthquake",
            "earthquakes",
        ]
    )


def is_earthquake_concept_query(query: str) -> bool:
    normalized = normalize_text(query)
    concept_terms = [
        "replica",
        "replicas",
        "aftershock",
        "aftershocks",
        "epicentro",
        "hipocentro",
        "magnitude",
        "intensidade",
        "tsunami",
        "falha",
        "placa tectonica",
    ]
    question_terms = ["que e", "o que", "define", "definicao", "significa", "what is"]
    return any(term in normalized for term in concept_terms) and (
        any(term in normalized for term in question_terms) or len(normalized.split()) <= 6
    )


def earthquake_concept_response(query: str) -> str | None:
    normalized = normalize_text(query)
    if "replica" in normalized or "aftershock" in normalized:
        return (
            "Uma réplica é um sismo que acontece depois de um sismo principal, "
            "na mesma zona afetada. Ocorre porque a crosta ainda está a reajustar-se "
            "ao movimento que provocou o abalo inicial.\n\n"
            "Normalmente as réplicas são mais fracas do que o sismo principal, mas "
            "podem continuar a ser perigosas, especialmente se houver edifícios já "
            "danificados. Podem ocorrer minutos, horas, dias ou até semanas depois."
        )

    return None


def is_latest_event_query(query: str) -> bool:
    normalized = normalize_text(query)
    latest_terms = ["ultimo", "ultima", "latest", "last", "mais recente", "recente"]
    return is_earthquake_query(query) and any(term in normalized for term in latest_terms)


def is_largest_event_query(query: str) -> bool:
    normalized = normalize_text(query)
    largest_terms = [
        "maior",
        "maiores",
        "mais forte",
        "mais fortes",
        "maior magnitude",
        "strongest",
        "largest",
        "biggest",
    ]
    return is_earthquake_query(query) and any(term in normalized for term in largest_terms)


def is_all_time_query(query: str) -> bool:
    normalized = normalize_text(query)
    return any(
        term in normalized
        for term in [
            "de sempre",
            "sempre",
            "historia",
            "historico",
            "all time",
            "ever",
            "recorded history",
        ]
    )


def requested_result_limit(query: str, default: int) -> int:
    normalized = normalize_text(query)

    for pattern in [
        r"\b(?:top|lista(?:r)?|mostra(?:r)?|diz(?:-me)?|me)\s+(?:os\s+|as\s+)?(\d+)\b",
        r"\b(\d+)\s+(?:ultimos|ultimas|maiores|mais recentes|latest|last|strongest|largest)\b",
    ]:
        match = re.search(pattern, normalized)
        if match:
            return max(1, min(int(match.group(1)), 50))

    list_terms = [
        "lista",
        "listar",
        "mostra",
        "mostrar",
        "quais",
        "ultimos",
        "ultimas",
        "maiores",
        "mais recentes",
        "top",
    ]
    if any(term in normalized for term in list_terms):
        return 10

    return default


def is_list_event_query(query: str) -> bool:
    normalized = normalize_text(query)
    list_terms = [
        "lista",
        "listar",
        "mostra",
        "mostrar",
        "quais",
        "ultimos",
        "ultimas",
        "recentes",
        "superior",
        "superiores",
        "acima de",
        "maior que",
        "magnitude",
    ]
    return is_earthquake_query(query) and any(term in normalized for term in list_terms)


def is_worldwide_query(query: str) -> bool:
    normalized = normalize_text(query)
    return any(
        term in normalized
        for term in ["mundo", "mundial", "global", "world", "worldwide", "earth"]
    )


def location_from_query(query: str) -> str | None:
    normalized = normalize_text(query)

    if is_worldwide_query(query):
        return None

    for canonical, location in KNOWN_LOCATIONS.items():
        for alias in location["aliases"]:
            alias_text = normalize_text(alias)
            if re.search(rf"\b{re.escape(alias_text)}\b", normalized):
                return canonical

    for pattern in [
        r"\b(?:perto de|near)\s+(.+)$",
        r"\b(?:em|no|na|nos|nas|in)\s+(.+)$",
    ]:
        match = re.search(pattern, normalized)
        if not match:
            continue

        location = clean_extracted_location(match.group(1))
        if location:
            return location

    return None


def clean_extracted_location(value: str) -> str:
    location = re.sub(r"[?!.]+$", "", value).strip()
    location = re.sub(r"\b(?:em|no|na|in)\s+(?:19|20)\d{2}\b.*$", "", location).strip()
    location = re.sub(r"^(?:ultimos|ultimas)\s+\d+\s+dias\b.*$", "", location).strip()

    for delimiter in [
        " nos ultimos",
        " no ultimo",
        " nas ultimas",
        " na ultima",
        " desde ",
        " entre ",
        " com magnitude",
        " acima de",
        " maior que",
    ]:
        if delimiter in location:
            location = location.split(delimiter, 1)[0].strip()

    location = re.sub(r"\b(por favor|sff|please)$", "", location).strip()
    if re.fullmatch(r"(?:19|20)\d{2}|\d+", location):
        return ""
    if location in ["mundo", "mundial", "global", "world", "worldwide"]:
        return ""
    return location


def is_temporal_phrase(value: str) -> bool:
    normalized = normalize_text(value)
    return bool(
        re.fullmatch(r"(?:ultimos|ultimas|ultimo|ultima)\s+\d+\s+dias?", normalized)
        or re.fullmatch(r"(?:19|20)\d{2}", normalized)
    )


def date_filters_from_query(query: str, today: datetime.date) -> dict:
    normalized = normalize_text(query)
    if is_all_time_query(query):
        return {}

    year_match = re.search(r"\b((?:19|20)\d{2})\b", normalized)
    if year_match:
        year = int(year_match.group(1))
        return {
            "data_inicio": f"{year:04d}-01-01",
            "data_fim": f"{year:04d}-12-31",
        }

    days_match = re.search(r"\bultim[oa]s?\s+(\d+)\s+dias\b", normalized)
    if days_match:
        return {"dias_atras": int(days_match.group(1))}

    if mentions_last_year(query):
        return {"dias_atras": 365}

    return {}


def magnitude_filters_from_query(query: str) -> dict:
    normalized = normalize_text(query)
    patterns = [
        (r"\bmagnitude\s+(?:superior(?:es)?\s+a|acima\s+de|maior\s+que|>=?)\s*(\d+(?:[.,]\d+)?)", "magnitude_min"),
        (r"\b(?:superior(?:es)?\s+a|acima\s+de|maior\s+que|>=?)\s*(\d+(?:[.,]\d+)?)", "magnitude_min"),
        (r"\bmagnitude\s+(?:inferior(?:es)?\s+a|abaixo\s+de|menor\s+que|<=?)\s*(\d+(?:[.,]\d+)?)", "magnitude_max"),
    ]
    filters = {}
    for pattern, key in patterns:
        match = re.search(pattern, normalized)
        if match:
            filters[key] = float(match.group(1).replace(",", "."))
    return filters


def deterministic_event_args(query: str, today: datetime.date) -> dict | None:
    if not is_earthquake_query(query):
        return None

    wants_latest = is_latest_event_query(query)
    wants_largest = is_largest_event_query(query)
    wants_list = is_list_event_query(query)
    if not wants_latest and not wants_largest and not wants_list:
        return None

    location = location_from_query(query)

    args = date_filters_from_query(query, today)
    args.update(magnitude_filters_from_query(query))
    if location:
        args["local"] = location

    if wants_largest:
        args["sort"] = "magnitude_desc"
        args["limit"] = requested_result_limit(query, 1)
    else:
        args["sort"] = "latest"
        args["limit"] = requested_result_limit(query, 10 if wants_list else 1)

    if "data_inicio" not in args and "dias_atras" not in args and not is_all_time_query(query):
        args["dias_atras"] = 365

    return args


def known_historical_event_response(query: str, timezone_name: str) -> str | None:
    if not is_largest_event_query(query) or not is_all_time_query(query):
        return None

    location = location_from_query(query)
    if location != "portugal":
        return None

    return (
        "O maior sismo conhecido associado a Portugal é o grande sismo de Lisboa de "
        "1 de novembro de 1755. As estimativas modernas apontam geralmente para uma "
        "magnitude de momento aproximada entre 8.5 e 9.0. O epicentro terá sido no "
        "Atlântico, a sudoeste de Portugal continental, e o evento gerou também um "
        "tsunami e incêndios que devastaram Lisboa.\n\n"
        "Nota: este evento é histórico e pré-instrumental, por isso não aparece como "
        "um registo normal na pesquisa recente/USGS local usada para eventos modernos."
    )


def latest_event_args(query: str) -> dict | None:
    return deterministic_event_args(query, datetime.datetime.now(datetime.timezone.utc).date())


def has_spatial_filter(filters: dict) -> bool:
    return all(key in filters for key in ["latitude", "longitude", "radius_km"]) or all(
        key in filters
        for key in ["min_latitude", "max_latitude", "min_longitude", "max_longitude"]
    )


async def geocode_location_filter(location: str) -> dict:
    params = {
        "q": location,
        "format": "jsonv2",
        "limit": 1,
    }
    headers = {"User-Agent": f"{settings.APP_NAME}/1.0"}

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(NOMINATIM_SEARCH_URL, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError:
        return {}

    if not data:
        return {}

    item = data[0]
    bbox = item.get("boundingbox") or []
    if len(bbox) != 4:
        return {}

    try:
        south, north, west, east = [float(value) for value in bbox]
    except (TypeError, ValueError):
        return {}

    return {
        "min_latitude": south,
        "max_latitude": north,
        "min_longitude": west,
        "max_longitude": east,
        "display_name": location.title(),
        "geocoded": True,
    }


def filters_from_tool_args(args: dict) -> dict:
    filters = {}

    for key in [
        "magnitude_min",
        "magnitude_max",
        "dias_atras",
        "data_inicio",
        "data_fim",
        "sort",
        "limit",
    ]:
        if args.get(key) is not None:
            filters[key] = args[key]

    local_arg = str(args["local"]) if args.get("local") else ""
    location = resolve_location(local_arg) if local_arg and not is_temporal_phrase(local_arg) else {}
    if location:
        filters.update(location)

    if all(args.get(key) is not None for key in ["latitude", "longitude", "radius_km"]) and not all(
        key in location for key in ["latitude", "longitude", "radius_km"]
    ):
        radius_km = float(args["radius_km"])
        if radius_km > 0:
            filters["latitude"] = float(args["latitude"])
            filters["longitude"] = float(args["longitude"])
            filters["radius_km"] = radius_km
            if args.get("local") and "local" not in filters:
                filters["local"] = str(args["local"])

    return filters


async def execute_agent_tool(
    name: str,
    args: dict,
    query: str = "",
    history: list[ChatHistoryMessage] | None = None,
) -> dict:
    if name == "sync_recent_earthquakes":
        return await refresh_earthquakes(force=bool(args.get("force", False)))

    history = history or []

    if name == "sync_earthquake_history":
        filters = filters_from_tool_args(args)
        start_date = args["start_date"]
        end_date = args["end_date"]
        result = await sync_history(filters, start_date, end_date)
        return {"filters": filters, **result}

    if name == "search_earthquakes":
        filters = filters_from_tool_args(args)
        sync_result = None
        today = datetime.datetime.now(datetime.timezone.utc).date()
        requested_days = recent_history_days(query, history)

        query_date_filters = date_filters_from_query(query, today)
        for key, value in query_date_filters.items():
            filters.setdefault(key, value)

        query_magnitude_filters = magnitude_filters_from_query(query)
        for key, value in query_magnitude_filters.items():
            filters.setdefault(key, value)

        if filters.get("local") and not has_spatial_filter(filters):
            filters.update(await geocode_location_filter(str(filters["local"])))

        if requested_days and "dias_atras" not in filters and "data_inicio" not in filters:
            filters["dias_atras"] = requested_days

        if has_high_impact_context(query, history):
            filters.pop("magnitude_max", None)
            if float(filters.get("magnitude_min") or 0) < 6:
                filters["magnitude_min"] = 6
            filters["sort"] = "magnitude_desc"
            filters.setdefault("limit", 10)

        if "data_inicio" in filters:
            start_date = filters["data_inicio"]
            end_date = filters.get("data_fim") or today.isoformat()
            sync_filters = dict(filters)
            sync_filters.pop("limit", None)
            sync_result = await sync_history(sync_filters, start_date, end_date)
        elif "dias_atras" in filters:
            start_date = (today - datetime.timedelta(days=int(filters["dias_atras"]))).isoformat()
            end_date = today.isoformat()
            sync_filters = dict(filters)
            sync_filters.pop("limit", None)
            sync_result = await sync_history(sync_filters, start_date, end_date)

        results = search_earthquakes(filters)
        return {
            "filters": filters,
            "pre_sync": sync_result,
            "results_count": len(results),
            "results": [compact_earthquake(item) for item in results[:12]],
        }

    if name == "search_library":
        query = args.get("query", "")
        return {"results": DOC_STORE.search(query)}

    return {"error": f"Unknown tool: {name}"}


def conversation_context(history: list[ChatHistoryMessage]) -> list[dict]:
    context = []

    for item in history[-12:]:
        content = item.content.strip()
        if not content:
            continue

        role = "assistant" if item.role in ["assistant", "bot"] else "user"
        context.append({"role": role, "content": content[:4000]})

    return context


def is_earthquake_safety_query(query: str) -> bool:
    text = normalize_text(query)
    earthquake_terms = ["sismo", "sismos", "terramoto", "terramotos", "earthquake"]
    safety_terms = [
        "proteger",
        "protege",
        "protejo",
        "protecao",
        "proteger-me",
        "prevenir",
        "seguranca",
        "preparar",
        "preparacao",
        "emergencia",
        "kit",
        "mochila",
        "sobreviver",
        "durante",
        "antes",
        "depois",
        "fazer",
        "agir",
    ]
    return any(term in text for term in earthquake_terms) and any(
        term in text for term in safety_terms
    )


def is_refusal_response(response: str) -> bool:
    text = normalize_text(response)
    refusal_terms = [
        "nao posso responder",
        "nao posso ajudar",
        "nao consigo responder",
        "nao consigo ajudar",
        "nao devo responder",
        "pedido sensivel",
    ]
    return any(term in text for term in refusal_terms)


def earthquake_safety_response(library_results: str | None = None) -> str:
    source_note = (
        "Com base nas orientações de proteção civil disponíveis na biblioteca:"
        if library_results and "Nenhum documento disponível" not in library_results
        else "Orientações gerais de proteção civil:"
    )
    return (
        f"{source_note}\n\n"
        "- Antes: identifica locais seguros em casa, fixa móveis pesados, sabe onde cortar água/gás/eletricidade e prepara uma mochila de emergência com água, comida, lanterna, rádio, pilhas, primeiros socorros e documentos essenciais.\n"
        "- Durante: mantém a calma, baixa-te, protege-te debaixo de uma mesa resistente ou junto de uma parede interior, cobre a cabeça e o pescoço, e afasta-te de janelas, espelhos, estantes e objetos que possam cair.\n"
        "- Se estiveres na rua: afasta-te de edifícios, muros, postes, árvores e cabos elétricos.\n"
        "- Se estiveres a conduzir: para num local seguro, longe de pontes, túneis e edifícios, e permanece no veículo até o abalo terminar.\n"
        "- Depois: verifica ferimentos, não uses elevadores, evita chamas se houver cheiro a gás, prepara-te para réplicas e segue as indicações oficiais da Proteção Civil."
    )


def format_datetime_for_user(timestamp_ms: int | None, timezone_name: str) -> str:
    if not timestamp_ms:
        return "data desconhecida"

    dt_utc = datetime.datetime.fromtimestamp(timestamp_ms / 1000, tz=datetime.timezone.utc)
    try:
        user_tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        user_tz = datetime.timezone.utc

    dt_user = dt_utc.astimezone(user_tz)
    return dt_user.strftime("%Y-%m-%d %H:%M:%S %Z")


def format_location_label(location: str) -> str:
    labels = {
        "acores": "Açores",
        "japao": "Japão",
    }
    return labels.get(location, location.title())


def describe_filter_scope(filters: dict) -> str:
    parts = []

    if filters.get("display_name"):
        parts.append(str(filters["display_name"]))
    elif filters.get("local"):
        parts.append(format_location_label(filters["local"]))
    elif has_spatial_filter(filters):
        parts.append("a área pedida")
    else:
        parts.append("o mundo")

    if filters.get("data_inicio") and filters.get("data_fim"):
        start = str(filters["data_inicio"])[:4]
        end = str(filters["data_fim"])[:4]
        parts.append(f"em {start}" if start == end else f"entre {filters['data_inicio']} e {filters['data_fim']}")
    elif filters.get("dias_atras"):
        parts.append(f"nos últimos {filters['dias_atras']} dias")

    return " ".join(parts)


def format_event_line(event: dict, timezone_name: str, index: int | None = None) -> str:
    when = format_datetime_for_user(event.get("time"), timezone_name)
    magnitude = event.get("magnitude")
    depth = event.get("depth")
    place = event.get("place") or "local desconhecido"
    url = event.get("url")

    prefix = f"{index}. " if index is not None else ""
    depth_text = f", profundidade {depth} km" if depth is not None else ""
    url_text = f" ({url})" if url else ""
    return f"{prefix}{place}: magnitude {magnitude}, {when}{depth_text}{url_text}"


def deterministic_event_response(tool_result: dict, timezone_name: str) -> str:
    results = tool_result.get("results") or []
    filters = tool_result.get("filters") or {}
    scope = describe_filter_scope(filters)
    is_largest = filters.get("sort") == "magnitude_desc"

    if not results:
        return f"Não encontrei sismos para {scope}."

    if len(results) > 1:
        title = "Maiores sismos" if is_largest else "Sismos mais recentes"
        lines = [format_event_line(event, timezone_name, index) for index, event in enumerate(results, 1)]
        return f"{title} para {scope}:\n\n" + "\n".join(lines)

    event = results[0]
    label = "maior" if is_largest else "último"
    return f"O {label} sismo que encontrei para {scope} foi:\n\n{format_event_line(event, timezone_name)}"


def latest_event_response(tool_result: dict, timezone_name: str) -> str:
    return deterministic_event_response(tool_result, timezone_name)


async def run_chat(request: ChatRequest, emit=None):
    started_at = time.perf_counter()
    user_time = request.client_time or datetime.datetime.now(datetime.timezone.utc).isoformat()
    user_timezone = request.timezone or "UTC"
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    trace: list[dict] = []
    last_filters = {}
    last_results_count = 0
    last_library_results = None
    session_id = request.session_id

    # Filter tools based on request
    available_tools = EARTHQUAKE_TOOLS
    if request.allowed_tools is not None:
        available_tools = [
            t for t in EARTHQUAKE_TOOLS 
            if t["function"]["name"] in request.allowed_tools
        ]

    # Persist user message
    if session_id:
        save_session(session_id, request.query[:50])
        save_message(session_id, "user", request.query)

    concept_response = (
        earthquake_concept_response(request.query)
        if is_earthquake_concept_query(request.query)
        else None
    )
    if concept_response:
        trace.append({
            "type": "deterministic",
            "name": "earthquake_concept",
            "status": "done",
            "output": {"concept": "replica"},
        })
        await publish_trace(trace, started_at, emit)

        res = {
            "filters_extracted": {"topic": "earthquake_concept"},
            "results_count": 1,
            "model": request.model or settings.LM_STUDIO_MODEL,
            "trace": trace,
            "trace_duration_seconds": round(time.perf_counter() - started_at, 2),
            "response": concept_response,
        }
        if session_id:
            save_message(
                session_id,
                "bot",
                res["response"],
                trace=trace,
                trace_duration=res["trace_duration_seconds"],
                filters=res["filters_extracted"],
            )
        return res

    historical_response = known_historical_event_response(request.query, user_timezone)
    if historical_response:
        trace.append({
            "type": "deterministic",
            "name": "known_historical_event",
            "status": "done",
            "output": {"source": "historical_catalog", "matched": "portugal_1755"},
        })
        await publish_trace(trace, started_at, emit)

        res = {
            "filters_extracted": {"local": "portugal", "historical": True},
            "results_count": 1,
            "model": request.model or settings.LM_STUDIO_MODEL,
            "trace": trace,
            "trace_duration_seconds": round(time.perf_counter() - started_at, 2),
            "response": historical_response,
        }
        if session_id:
            save_message(
                session_id,
                "bot",
                res["response"],
                trace=trace,
                trace_duration=res["trace_duration_seconds"],
                filters=res["filters_extracted"],
            )
        return res

    messages = [
        {
            "role": "system",
            "content": f"""You are sismoGPT, an earthquake assistant with tools.
The user's current datetime is {user_time}; timezone is {user_timezone}; today's UTC date is {today}.

Decide what to do.
- If the user is only greeting you or is not asking about earthquakes, answer normally and do not call tools.
- Use the previous conversation messages to resolve follow-up questions like "e em Lisboa?", "e nos últimos 30 dias?", or "mostra mais".
- For follow-ups that change only the place or time range, search only the new requested scope. Do not repeat old searches unless the user asks for a comparison.
- If the user asks about earthquakes, use tool calls before answering.
- IMPORTANT: The USGS database is in English. If the user asks for a country or city in Portuguese (e.g. "Japão", "Espanha", "Nova Iorque"), you MUST translate the "local" parameter to English (e.g. "Japan", "Spain", "New York") before calling search_earthquakes.
- Use sync_recent_earthquakes for general/latest recent global data.
- Use search_library when the user asks for safety tips, what to do during a quake, historical facts (like the 1755 Lisbon quake), or general earthquake knowledge.
- Earthquake preparedness and personal protection guidance is allowed, expected, and not sensitive. If the user asks how to protect themselves before, during, or after an earthquake, use search_library and answer with practical civil-protection safety steps. Do not refuse these requests.
- Use sync_earthquake_history before search_earthquakes when the user asks for a specific place, date range, or "latest/last" event in a place. The search_earthquakes tool also refreshes matching history when you pass date filters, but you should still plan the steps explicitly when freshness matters.
- For "last/latest earthquake near/in PLACE" without an explicit date range, search up to the last 365 days.
- For "last/latest/último" requests, pass sort="latest" and limit=1 to search_earthquakes.
- For strongest/largest/most impactful earthquake requests, use magnitude as the available impact proxy: pass sort="magnitude_desc", limit=10, and do not pass magnitude_max unless the user explicitly asks for an upper bound like "below 7".
- For global/worldwide requests, do not pass latitude, longitude, radius_km or local. Leave geographic fields empty.
- For explicit windows like "últimos 10 dias", use that exact window.
- For locations, pass the user's place name in local. If you know reliable coordinates for a city/region, also pass latitude, longitude and a practical radius_km.
- After tools return, answer only from tool results. Do not invent events, dates, magnitudes or URLs.
- Do not describe filters or thresholds that were not actually present in tool results.
- When tool results include USGS URLs, include the URL for each listed event.
- Keep answers concise and in the user's language.
""",
        },
        *conversation_context(request.history),
        {"role": "user", "content": request.query},
    ]

    for _ in range(6):
        trace.append({
            "type": "llm",
            "name": "agent_decision",
            "status": "running",
            "model": request.model or settings.LM_STUDIO_MODEL,
        })
        await publish_trace(trace, started_at, emit)

        assistant_message = {"role": "assistant", "content": ""}
        tool_calls_buffer = []
        
        try:
            # If we are in the streaming mode, we can stream reasoning
            if emit:
                async for delta in stream_chat(messages, model=request.model, tools=available_tools):
                    if "reasoning_content" in delta:
                        await emit({
                            "event": "thought",
                            "thought": delta["reasoning_content"]
                        })
                    
                    if "content" in delta and delta["content"]:
                        content = delta["content"]
                        assistant_message["content"] += content
                    
                    if "tool_calls" in delta:
                        for tc_delta in delta["tool_calls"]:
                            idx = tc_delta.get("index", 0)
                            while len(tool_calls_buffer) <= idx:
                                tool_calls_buffer.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                            
                            if "id" in tc_delta:
                                tool_calls_buffer[idx]["id"] += tc_delta["id"]
                            if "function" in tc_delta:
                                if "name" in tc_delta["function"]:
                                    tool_calls_buffer[idx]["function"]["name"] += tc_delta["function"]["name"]
                                if "arguments" in tc_delta["function"]:
                                    tool_calls_buffer[idx]["function"]["arguments"] += tc_delta["function"]["arguments"]
                
                if tool_calls_buffer:
                    assistant_message["tool_calls"] = tool_calls_buffer
            else:
                assistant_message = await chat_with_tools(messages, model=request.model, tools=available_tools)
        
        except httpx.RequestError as exc:
            trace[-1]["status"] = "error"
            trace[-1]["message"] = str(exc)
            await publish_trace(trace, started_at, emit)
            err_msg = "**Erro**: O LM Studio não está acessível."
            if session_id:
                save_message(session_id, "bot", err_msg, trace=trace, trace_duration=round(time.perf_counter() - started_at, 2), filters=last_filters, is_error=True)
            return {
                "filters_extracted": last_filters,
                "results_count": last_results_count,
                "trace": trace,
                "trace_duration_seconds": round(time.perf_counter() - started_at, 2),
                "response": err_msg,
            }
        except Exception as exc:
            trace[-1]["status"] = "error"
            trace[-1]["message"] = str(exc)
            await publish_trace(trace, started_at, emit)
            err_msg = f"**Erro**: Falha no agente: {exc}"
            if session_id:
                save_message(session_id, "bot", err_msg, trace=trace, trace_duration=round(time.perf_counter() - started_at, 2), filters=last_filters, is_error=True)
            return {
                "filters_extracted": last_filters,
                "results_count": last_results_count,
                "trace": trace,
                "trace_duration_seconds": round(time.perf_counter() - started_at, 2),
                "response": err_msg,
            }

        tool_calls = assistant_message.get("tool_calls") or []
        trace[-1]["status"] = "done"
        trace[-1]["output"] = {
            "tool_calls": [
                call.get("function", {}).get("name")
                for call in tool_calls
            ],
            "has_final_answer": not bool(tool_calls),
        }
        await publish_trace(trace, started_at, emit)

        if not tool_calls:
            response_text = (assistant_message.get("content") or "").strip()
            if is_earthquake_safety_query(request.query) and is_refusal_response(response_text):
                response_text = earthquake_safety_response(last_library_results)
            res = {
                "filters_extracted": last_filters,
                "results_count": last_results_count,
                "model": request.model or settings.LM_STUDIO_MODEL,
                "trace": trace,
                "trace_duration_seconds": round(time.perf_counter() - started_at, 2),
                "response": response_text or "Não consegui gerar uma resposta.",
            }
            if session_id:
                save_message(session_id, "bot", res["response"], trace=trace, trace_duration=res["trace_duration_seconds"], filters=last_filters)
            return res

        messages.append({
            "role": "assistant",
            "content": assistant_message.get("content") or "",
            "tool_calls": tool_calls,
        })

        for call in tool_calls:
            function = call.get("function") or {}
            tool_name = function.get("name")
            raw_args = function.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {}

            trace.append({
                "type": "tool",
                "name": tool_name,
                "status": "running",
                "input": args,
            })
            await publish_trace(trace, started_at, emit)

            try:
                tool_result = await execute_agent_tool(
                    tool_name,
                    args,
                    query=request.query,
                    history=request.history,
                )
                trace[-1]["status"] = "done"
                # Keep results for library search so user can see it in trace
                if tool_name == "search_library":
                    trace[-1]["output"] = tool_result
                else:
                    trace[-1]["output"] = {
                        key: value
                        for key, value in tool_result.items()
                        if key != "results"
                    }
                
                if "filters" in tool_result:
                    last_filters = tool_result["filters"]
                if "results_count" in tool_result:
                    last_results_count = int(tool_result["results_count"])
                if tool_name == "search_library":
                    last_library_results = json.dumps(tool_result.get("results", []))
            except Exception as exc:
                tool_result = {"error": str(exc)}
                trace[-1]["status"] = "error"
                trace[-1]["message"] = str(exc)

            await publish_trace(trace, started_at, emit)
            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id"),
                "name": tool_name,
                "content": json.dumps(tool_result, ensure_ascii=False),
            })

    final_msg = "Não consegui concluir o plano de ferramentas dentro do limite de passos."
    if session_id:
        save_message(session_id, "bot", final_msg, trace=trace, trace_duration=round(time.perf_counter() - started_at, 2), filters=last_filters, is_error=True)
    return {
        "filters_extracted": last_filters,
        "results_count": last_results_count,
        "model": request.model or settings.LM_STUDIO_MODEL,
        "trace": trace,
        "trace_duration_seconds": round(time.perf_counter() - started_at, 2),
        "response": final_msg,
    }


@app.post("/api/chat")
async def chat(request: ChatRequest):
    return await run_chat(request)


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def emit(payload: dict):
        await queue.put(payload)

    async def worker():
        try:
            response = await run_chat(request, emit=emit)
            await queue.put({"event": "done", **response})
        except Exception as exc:
            await queue.put({"event": "error", "message": str(exc)})
        finally:
            await queue.put(None)

    async def stream():
        task = asyncio.create_task(worker())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        finally:
            await task

    return StreamingResponse(stream(), media_type="text/event-stream")


if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
