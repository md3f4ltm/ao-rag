from contextlib import asynccontextmanager
import asyncio
import json
import time

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
import os
import datetime
from pydantic import BaseModel
import httpx
from app.config import settings
from app.lmstudio import extract_filters, generate_answer, list_models
from app.earthquake_store import (
    count_earthquakes,
    get_last_sync,
    init_db,
    refresh_earthquakes,
    search_earthquakes,
    sync_history,
)
from app.query_filters import merge_filters


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        await refresh_earthquakes()
    except httpx.HTTPError as exc:
        print(f"USGS sync failed on startup: {exc}")
    yield


app = FastAPI(title="sismoGPT API", lifespan=lifespan)

# Mount static files
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

class ChatRequest(BaseModel):
    query: str
    model: str | None = None
    client_time: str | None = None
    timezone: str | None = None


def default_history_window() -> tuple[str, str]:
    end = datetime.datetime.now(datetime.timezone.utc).date()
    start = end - datetime.timedelta(days=30)
    return start.isoformat(), end.isoformat()


def query_asks_latest(filters: dict) -> bool:
    return filters.get("sort") == "latest"


def requested_date_range(filters: dict) -> tuple[str, str] | None:
    if "data_inicio" in filters:
        end = filters.get("data_fim") or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        return filters["data_inicio"], end
    return None


def recent_date_range(filters: dict) -> tuple[str, str] | None:
    if filters.get("sort") == "latest" and filters.get("limit") and "dias_atras" not in filters:
        end = datetime.datetime.now(datetime.timezone.utc).date()
        start = end - datetime.timedelta(days=365)
        return start.isoformat(), end.isoformat()

    if "dias_atras" not in filters:
        return None

    end = datetime.datetime.now(datetime.timezone.utc).date()
    start = end - datetime.timedelta(days=int(filters["dias_atras"]))
    return start.isoformat(), end.isoformat()


def can_auto_sync_history(filters: dict, start_date: str, end_date: str) -> bool:
    start = datetime.datetime.fromisoformat(start_date)
    end = datetime.datetime.fromisoformat(end_date)
    days = abs((end - start).days)
    has_geo = all(key in filters for key in ["latitude", "longitude", "radius_km"])
    has_strong_mag_filter = filters.get("magnitude_min", 0) >= 4
    return has_geo or has_strong_mag_filter or days <= 366

def format_response(filters: dict, results: list):
    if not results:
        period = f" nos últimos {filters['dias_atras']} dias" if "dias_atras" in filters else ""
        if all(key in filters for key in ["local", "radius_km"]):
            return (
                f"Não encontrei sismos perto de {filters['local']} "
                f"num raio de {filters['radius_km']} km{period} com os critérios especificados."
            )
        return f"Não encontrei sismos{period} com os critérios especificados."
        
    count = len(results)
    
    response = f"Encontrei {count} sismo(s)"
    if "local" in filters:
        response += f" em '{filters['local']}'"
    if "magnitude_min" in filters:
        response += f" com magnitude acima de {filters['magnitude_min']}"
        
    response += ".\n\nAqui estão os mais recentes:\n"
    
    # Show up to 5 results
    for eq in results[:5]:
        dt = datetime.datetime.fromtimestamp(eq["time"] / 1000, tz=datetime.timezone.utc)
        date_str = dt.strftime("%d/%m/%Y %H:%M")
        mag = eq["magnitude"]
        place = eq["place"]
        distance = f" ({eq['distance_km']} km aprox.)" if "distance_km" in eq else ""
        response += f"- {date_str}: Magnitude {mag} - {place}{distance}\n"
        
    return response

@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return f.read()
    return "Index not found. Please create static/index.html"


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


async def run_chat(request: ChatRequest, emit=None):
    started_at = time.perf_counter()
    user_time = request.client_time or datetime.datetime.now(datetime.timezone.utc).isoformat()
    user_timezone = request.timezone or "UTC"
    trace = [
        {
            "type": "llm",
            "name": "extract_filters",
            "status": "running",
            "model": request.model or settings.LM_STUDIO_MODEL,
            "input": {"user_time": user_time, "timezone": user_timezone},
        }
    ]
    await publish_trace(trace, started_at, emit)

    # 1. Ask LLM to extract filters
    result = await extract_filters(
        request.query,
        model=request.model,
        user_time=user_time,
        user_timezone=user_timezone,
    )
    
    if result.get("status") == "error":
        trace[-1]["status"] = "error"
        trace[-1]["message"] = result.get("message")
        await publish_trace(trace, started_at, emit)
        return {
            "filters_extracted": {},
            "results_count": 0,
            "trace": trace,
            "trace_duration_seconds": round(time.perf_counter() - started_at, 2),
            "response": f"**Erro**: {result.get('message')}"
        }

    filters = merge_filters(result.get("filters", {}), request.query)
    trace[-1]["status"] = "done"
    trace[-1]["output"] = filters
    await publish_trace(trace, started_at, emit)

    sync_actions = []

    # 2. Keep the local SQLite database fresh, then query it.
    try:
        recent_sync = await refresh_earthquakes()
        trace.append({
            "type": "tool",
            "name": "sync_recent",
            "status": "done",
            "output": recent_sync,
        })
        await publish_trace(trace, started_at, emit)
    except httpx.HTTPError as exc:
        trace.append({
            "type": "tool",
            "name": "sync_recent",
            "status": "error",
            "message": str(exc),
        })
        await publish_trace(trace, started_at, emit)
        print(f"USGS sync failed during chat: {exc}")

    date_range = requested_date_range(filters)
    api_range = date_range or recent_date_range(filters)

    should_sync_first = query_asks_latest(filters) and api_range and can_auto_sync_history(filters, *api_range)

    if should_sync_first:
        trace.append({
            "type": "tool",
            "name": "search_usgs_api",
            "status": "running",
            "input": {
                "start_date": api_range[0],
                "end_date": api_range[1],
                "filters": filters,
            },
        })
        await publish_trace(trace, started_at, emit)
        try:
            sync_result = await sync_history(filters, *api_range)
            sync_actions.append(sync_result)
            trace[-1]["status"] = "done"
            trace[-1]["output"] = sync_result
            await publish_trace(trace, started_at, emit)
        except httpx.HTTPError as exc:
            trace[-1]["status"] = "error"
            trace[-1]["message"] = str(exc)
            await publish_trace(trace, started_at, emit)
            print(f"USGS API search failed during chat: {exc}")

    results = search_earthquakes(filters)
    trace.append({
        "type": "tool",
        "name": "search_database",
        "status": "done",
        "input": filters,
        "output": {"results_count": len(results), "after_api": should_sync_first},
    })
    await publish_trace(trace, started_at, emit)

    if not results and not should_sync_first and api_range and can_auto_sync_history(filters, *api_range):
        trace.append({
            "type": "tool",
            "name": "search_usgs_api",
            "status": "running",
            "input": {
                "start_date": api_range[0],
                "end_date": api_range[1],
                "filters": filters,
            },
        })
        await publish_trace(trace, started_at, emit)
        try:
            sync_result = await sync_history(filters, *api_range)
            sync_actions.append(sync_result)
            trace[-1]["status"] = "done"
            trace[-1]["output"] = sync_result
            await publish_trace(trace, started_at, emit)
        except httpx.HTTPError as exc:
            trace[-1]["status"] = "error"
            trace[-1]["message"] = str(exc)
            await publish_trace(trace, started_at, emit)
            print(f"USGS API search failed during chat: {exc}")

        results = search_earthquakes(filters)
        trace.append({
            "type": "tool",
            "name": "search_database",
            "status": "done",
            "input": filters,
            "output": {"results_count": len(results), "after_api": True},
        })
        await publish_trace(trace, started_at, emit)

    if (
        not results
        and all(key in filters for key in ["latitude", "longitude", "radius_km"])
        and not query_asks_latest(filters)
    ):
        start_date, end_date = date_range or default_history_window()
        trace.append({
            "type": "tool",
            "name": "sync_history_fallback",
            "status": "running",
            "input": {"start_date": start_date, "end_date": end_date},
        })
        await publish_trace(trace, started_at, emit)
        try:
            sync_result = await sync_history(filters, start_date, end_date)
            sync_actions.append(sync_result)
            trace[-1]["status"] = "done"
            trace[-1]["output"] = sync_result
            await publish_trace(trace, started_at, emit)
            results = search_earthquakes(filters)
            trace.append({
                "type": "tool",
                "name": "search_database",
                "status": "done",
                "input": filters,
                "output": {"results_count": len(results), "after_sync": True},
            })
            await publish_trace(trace, started_at, emit)
        except httpx.HTTPError as exc:
            trace[-1]["status"] = "error"
            trace[-1]["message"] = str(exc)
            await publish_trace(trace, started_at, emit)
            print(f"USGS fallback history sync failed during chat: {exc}")
    
    # 3. Ask the selected LLM to write the final grounded answer from DB results.
    trace.append({
        "type": "llm",
        "name": "final_answer",
        "status": "running",
        "model": request.model or settings.LM_STUDIO_MODEL,
        "input": {"results_count": len(results)},
    })
    await publish_trace(trace, started_at, emit)
    answer = await generate_answer(
        request.query,
        filters,
        results,
        model=request.model,
        user_time=user_time,
        user_timezone=user_timezone,
    )
    response_text = (
        answer["answer"]
        if answer.get("status") == "success"
        else format_response(filters, results)
    )
    model_used = answer.get("model", request.model or settings.LM_STUDIO_MODEL)
    trace[-1]["status"] = answer.get("status", "done")
    trace[-1]["model"] = model_used
    if answer.get("status") != "success":
        trace[-1]["message"] = answer.get("message")
    await publish_trace(trace, started_at, emit)

    trace_duration_seconds = round(time.perf_counter() - started_at, 2)
    
    return {
        "filters_extracted": filters,
        "results_count": len(results),
        "model": model_used,
        "sync_actions": sync_actions,
        "trace": trace,
        "trace_duration_seconds": trace_duration_seconds,
        "response": response_text
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
