import httpx
from app.config import settings
import json

class LMStudioError(Exception):
    pass

async def extract_filters(query: str) -> dict:
    url = f"{settings.LM_STUDIO_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.LM_STUDIO_API_KEY}"}
    
    system_prompt = """You are an assistant that extracts filters for an earthquake dataset from a user query.
Return ONLY a valid JSON object. Do not include markdown formatting like ```json.
Possible keys:
- "local": string (name of the country, city or region)
- "magnitude_min": float
- "magnitude_max": float
- "dias_atras": integer (if the user asks for last X days)
If a filter is not mentioned, do not include it.

Examples:
Input: "Sismos acima de magnitude 4 em Portugal"
Output: {"local": "Portugal", "magnitude_min": 4}

Input: "Qual foi o último sismo nos Açores?"
Output: {"local": "Açores"}

Input: "Sismos hoje na Califórnia"
Output: {"local": "Califórnia", "dias_atras": 1}
"""

    payload = {
        "model": settings.LM_STUDIO_MODEL,
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

