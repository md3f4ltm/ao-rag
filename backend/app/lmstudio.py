import httpx
from app.config import settings

class LMStudioError(Exception):
    pass


EARTHQUAKE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "sync_recent_earthquakes",
            "description": "Refresh the local earthquake cache from the USGS all-month feed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "force": {
                        "type": "boolean",
                        "description": "Force a refresh even when the cache is fresh.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sync_earthquake_history",
            "description": "Fetch earthquake history from the USGS API for a date range and optional geographic/magnitude filters, then store it locally.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD.",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD.",
                    },
                    "local": {
                        "type": "string",
                        "description": "Requested place name, for example Lisboa, Portugal, Açores, Japan.",
                    },
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "radius_km": {
                        "type": "number",
                        "description": "Radius in kilometers for searches near a point.",
                    },
                    "magnitude_min": {"type": "number"},
                    "limit": {"type": "integer"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_earthquakes",
            "description": "Search the local earthquake database using optional place, date, magnitude, sorting and limit filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "local": {
                        "type": "string",
                        "description": "Requested place name, for example Lisboa, Portugal, Açores, Japan.",
                    },
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "radius_km": {
                        "type": "number",
                        "description": "Radius in kilometers for searches near a point.",
                    },
                    "magnitude_min": {"type": "number"},
                    "magnitude_max": {"type": "number"},
                    "dias_atras": {
                        "type": "integer",
                        "description": "Number of days backwards from the current date.",
                    },
                    "data_inicio": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD.",
                    },
                    "data_fim": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD.",
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["latest"],
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 500,
                    },
                },
                "required": [],
            },
        },
    },
]


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


async def chat_with_tools(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.1,
) -> dict:
    url = f"{settings.LM_STUDIO_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.LM_STUDIO_API_KEY}"}
    payload = {
        "model": usable_model(model),
        "messages": messages,
        "tools": EARTHQUAKE_TOOLS,
        "tool_choice": "auto",
        "temperature": temperature,
    }

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    return data["choices"][0]["message"]
