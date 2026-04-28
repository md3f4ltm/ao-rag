import httpx
import asyncio
from app.config import settings


class LMStudioError(Exception):
    pass


async def list_models():
    url = f"{settings.LM_STUDIO_BASE_URL}/models"

    headers = {"Authorization": f"Bearer {settings.LM_STUDIO_API_KEY}"}

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(url, headers=headers)

    if response.status_code != 200:
        raise LMStudioError(
            f"Failed to list models: {response.status_code} - {response.text}"
        )
    data = response.json()
    models = data.get("data", [])
    return [model["id"] for model in models]


async def main():
    models = await list_models()

    print("Models found:")
    for model in models:
        print(f"- {model}")


if __name__ == "__main__":
    asyncio.run(main())
