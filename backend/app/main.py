from contextlib import asynccontextmanager
import asyncio
import json
import time

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
import datetime
from pathlib import Path
from pydantic import BaseModel, Field
import httpx
from app.config import settings
from app.lmstudio import chat_with_tools, list_models
from app.earthquake_store import (
    count_earthquakes,
    get_last_sync,
    init_db,
    refresh_earthquakes,
    search_earthquakes,
    sync_history,
)
from app.query_filters import resolve_location


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
    model: str | None = None
    client_time: str | None = None
    timezone: str | None = None
    history: list[ChatHistoryMessage] = Field(default_factory=list)


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

    location = resolve_location(str(args["local"])) if args.get("local") else {}
    if location:
        filters.update(location)

    if all(args.get(key) is not None for key in ["latitude", "longitude", "radius_km"]) and not all(
        key in location for key in ["latitude", "longitude", "radius_km"]
    ):
        filters["latitude"] = float(args["latitude"])
        filters["longitude"] = float(args["longitude"])
        filters["radius_km"] = float(args["radius_km"])
        if args.get("local") and "local" not in filters:
            filters["local"] = str(args["local"])

    return filters


async def execute_agent_tool(name: str, args: dict) -> dict:
    if name == "sync_recent_earthquakes":
        return await refresh_earthquakes(force=bool(args.get("force", False)))

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

        if "data_inicio" in filters:
            start_date = filters["data_inicio"]
            end_date = filters.get("data_fim") or today.isoformat()
            sync_result = await sync_history(filters, start_date, end_date)
        elif "dias_atras" in filters and (
            filters.get("local")
            or all(key in filters for key in ["latitude", "longitude", "radius_km"])
            or all(
                key in filters
                for key in ["min_latitude", "max_latitude", "min_longitude", "max_longitude"]
            )
        ):
            start_date = (today - datetime.timedelta(days=int(filters["dias_atras"]))).isoformat()
            end_date = today.isoformat()
            sync_result = await sync_history(filters, start_date, end_date)

        results = search_earthquakes(filters)
        return {
            "filters": filters,
            "pre_sync": sync_result,
            "results_count": len(results),
            "results": [compact_earthquake(item) for item in results[:12]],
        }

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


async def run_chat(request: ChatRequest, emit=None):
    started_at = time.perf_counter()
    user_time = request.client_time or datetime.datetime.now(datetime.timezone.utc).isoformat()
    user_timezone = request.timezone or "UTC"
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    trace: list[dict] = []
    last_filters = {}
    last_results_count = 0

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
- Use sync_recent_earthquakes for general/latest recent global data.
- Use sync_earthquake_history before search_earthquakes when the user asks for a specific place, date range, or "latest/last" event in a place. The search_earthquakes tool also refreshes matching history when you pass date filters, but you should still plan the steps explicitly when freshness matters.
- For "last/latest earthquake near/in PLACE" without an explicit date range, search up to the last 365 days.
- For "last/latest/último" requests, pass sort="latest" and limit=1 to search_earthquakes.
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

        try:
            assistant_message = await chat_with_tools(messages, model=request.model)
        except httpx.RequestError as exc:
            trace[-1]["status"] = "error"
            trace[-1]["message"] = str(exc)
            await publish_trace(trace, started_at, emit)
            return {
                "filters_extracted": last_filters,
                "results_count": last_results_count,
                "trace": trace,
                "trace_duration_seconds": round(time.perf_counter() - started_at, 2),
                "response": "**Erro**: O LM Studio não está acessível.",
            }
        except Exception as exc:
            trace[-1]["status"] = "error"
            trace[-1]["message"] = str(exc)
            await publish_trace(trace, started_at, emit)
            return {
                "filters_extracted": last_filters,
                "results_count": last_results_count,
                "trace": trace,
                "trace_duration_seconds": round(time.perf_counter() - started_at, 2),
                "response": f"**Erro**: Falha no agente: {exc}",
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
            return {
                "filters_extracted": last_filters,
                "results_count": last_results_count,
                "model": request.model or settings.LM_STUDIO_MODEL,
                "trace": trace,
                "trace_duration_seconds": round(time.perf_counter() - started_at, 2),
                "response": response_text or "Não consegui gerar uma resposta.",
            }

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
                tool_result = await execute_agent_tool(tool_name, args)
                trace[-1]["status"] = "done"
                trace[-1]["output"] = {
                    key: value
                    for key, value in tool_result.items()
                    if key != "results"
                }
                if "filters" in tool_result:
                    last_filters = tool_result["filters"]
                if "results_count" in tool_result:
                    last_results_count = int(tool_result["results_count"])
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

    return {
        "filters_extracted": last_filters,
        "results_count": last_results_count,
        "model": request.model or settings.LM_STUDIO_MODEL,
        "trace": trace,
        "trace_duration_seconds": round(time.perf_counter() - started_at, 2),
        "response": "Não consegui concluir o plano de ferramentas dentro do limite de passos.",
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
