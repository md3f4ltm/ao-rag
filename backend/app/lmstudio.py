import httpx
from app.config import settings
import json
import datetime

class LMStudioError(Exception):
    pass


async def list_models() -> list[str]:
    url = f"{settings.LM_STUDIO_BASE_URL}/models"
    headers = {"Authorization": f"Bearer {settings.LM_STUDIO_API_KEY}"}

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

    return [model["id"] for model in data.get("data", []) if model.get("id")]


def usable_model(model: str | None) -> str:
    if not model or model == "local-model" or "embedding" in model.lower():
        return settings.LM_STUDIO_MODEL
    return model


async def extract_filters(
    query: str,
    model: str | None = None,
    user_time: str | None = None,
    user_timezone: str | None = None,
) -> dict:
    url = f"{settings.LM_STUDIO_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.LM_STUDIO_API_KEY}"}
    
    system_prompt = f"""You are preparing arguments for an earthquake database/API search tool.
Return ONLY one valid JSON object with tool arguments. Do not include markdown formatting like ```json.
The user's current datetime is: {user_time or "unknown"}.
The user's timezone is: {user_timezone or "unknown"}.

Tool argument schema and exact meaning:
- "local": geographic name requested by the user. Use country/city/region names only. Examples: "Portugal", "Lisboa", "Açores", "Madeira", "Japan".
- "magnitude_min": minimum magnitude filter. Use only for phrases like "magnitude acima de 4", "maior que 5", "M>=3".
- "magnitude_max": maximum magnitude filter. Use only for phrases like "abaixo de 4", "menor que 3".
- "dias_atras": time window in days counted backwards from the user's current datetime. Use ONLY when the user explicitly asks for a day window, e.g. "últimos 7 dias", "last 24 hours", "hoje".
- "data_inicio": absolute start date in YYYY-MM-DD. Use for "desde 2020", "from 2024-01-01", "em 2023".
- "data_fim": absolute end date in YYYY-MM-DD. Use with "data_inicio" when there is a bounded year/date range.
- "sort": set to "latest" when the user asks for latest/last/most recent events.
- "limit": number of result rows requested. Use for "10 sismos", "top 10", "os 10 últimos", "10 mais recentes".

Important disambiguation rules:
- A number before/near "sismos", "terremotos", "earthquakes", "resultados", "mais recentes", "últimos" is a result count: use "limit".
- A number before/near "dias", "days", "horas", "hours", "semanas", "weeks", "anos", "years" is a time window: use "dias_atras" or absolute dates.
- Never convert "10 mais recentes" into "dias_atras": 10. It means "limit": 10.
- "10 mais recentes em Portugal" means {{"local": "Portugal", "sort": "latest", "limit": 10}}.
- "os 10 últimos sismos em Portugal" means {{"local": "Portugal", "sort": "latest", "limit": 10}}.
- "sismos em Portugal nos últimos 10 dias" means {{"local": "Portugal", "dias_atras": 10}}.
- "último sismo em Lisboa" means {{"local": "Lisboa", "sort": "latest", "limit": 1}}.
- "hoje" means {{"dias_atras": 1}}.
- If the user gives a year range or "desde 2020", use "data_inicio"/"data_fim".
- If the user asks for "mais recentes" without a number, use {{"sort": "latest", "limit": 10}}.

If a filter is not mentioned, do not include it.
Understand Portuguese and English location names. Preserve the user's intended location even if it is written in English.
Examples of equivalents: Lisbon/Lisboa, Azores/Açores, Oporto/Porto.

Examples:
Input: "Sismos acima de magnitude 4 em Portugal"
Output: {{"local": "Portugal", "magnitude_min": 4}}

Input: "Qual foi o último sismo nos Açores?"
Output: {{"local": "Açores", "sort": "latest", "limit": 1}}

Input: "Sismos hoje na Califórnia"
Output: {{"local": "Califórnia", "dias_atras": 1}}

Input: "Sismos perto de Lisboa desde 2020"
Output: {{"local": "Lisboa", "data_inicio": "2020-01-01"}}

Input: "10 mais recentes em Portugal"
Output: {{"local": "Portugal", "sort": "latest", "limit": 10}}

Input: "os 10 últimos sismos em Portugal"
Output: {{"local": "Portugal", "sort": "latest", "limit": 10}}

Input: "sismos em Portugal nos últimos 10 dias"
Output: {{"local": "Portugal", "dias_atras": 10}}
"""

    payload = {
        "model": usable_model(model),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ],
        "temperature": 0.1
    }

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # Try to parse as JSON
            # Sometimes LLMs add markdown json blocks anyway
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
                
            return {"status": "success", "filters": json.loads(content.strip())}
        except httpx.RequestError as e:
            print(f"Connection Error in extract_filters: {e}")
            return {"status": "error", "message": "O LM Studio não está acessível. Verifique se o servidor local está a correr."}
        except Exception as e:
            print(f"Error in extract_filters: {e}")
            return {"status": "error", "message": f"Erro interno ao processar a resposta do LLM: {str(e)}"}


async def generate_answer(
    query: str,
    filters: dict,
    results: list[dict],
    model: str | None = None,
    user_time: str | None = None,
    user_timezone: str | None = None,
) -> dict:
    url = f"{settings.LM_STUDIO_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.LM_STUDIO_API_KEY}"}

    compact_results = [
        {
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
        for item in results[:12]
    ]

    system_prompt = f"""You are sismoGPT, a grounded earthquake assistant.
Answer in the same language as the user, normally Portuguese if the user writes Portuguese.
The user's current datetime is: {user_time or "unknown"}.
The user's timezone is: {user_timezone or "unknown"}.
You have already used a database search tool. Use ONLY the provided database results and filters.
Do not invent earthquakes, magnitudes, dates, locations, or sources.
If there are no results, explain that no matching events were found and suggest a practical broader query.
If the query asks for "latest" and the filters include dias_atras, explicitly mention that the search was limited to that recent window.
If the user asks for N results and fewer are available, say how many were found.
For lists, include date/time UTC, magnitude, place, depth, and the USGS URL for each event.
Keep the answer concise but useful. Mention that the source is USGS.
"""

    payload = {
        "model": usable_model(model),
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "user_query": query,
                        "user_time": user_time,
                        "user_timezone": user_timezone,
                        "filters_used": filters,
                        "results_count": len(results),
                        "database_results": compact_results,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0.4,
    }

    async with httpx.AsyncClient(timeout=90) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return {
                "status": "success",
                "answer": data["choices"][0]["message"]["content"].strip(),
                "model": usable_model(model),
            }
        except httpx.RequestError as e:
            print(f"Connection Error in generate_answer: {e}")
            return {"status": "error", "message": "O LM Studio não está acessível."}
        except Exception as e:
            print(f"Error in generate_answer: {e}")
            return {"status": "error", "message": f"Erro ao gerar a resposta final: {str(e)}"}
