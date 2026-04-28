from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import json
import os
import datetime
from pydantic import BaseModel
from app.lmstudio import extract_filters

app = FastAPI(title="SeismoGPT API")

# Load earthquake data
DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "earthquakes.json")
earthquakes = []
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        earthquakes = json.load(f)

# Mount static files
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

class ChatRequest(BaseModel):
    query: str

def filter_earthquakes(filters: dict):
    filtered = earthquakes
    
    if "local" in filters:
        local_lower = filters["local"].lower()
        # the place field usually contains something like "5 km W of Somewhere, Portugal"
        filtered = [eq for eq in filtered if eq["place"] and local_lower in eq["place"].lower()]
        
    if "magnitude_min" in filters:
        min_mag = filters["magnitude_min"]
        filtered = [eq for eq in filtered if eq["magnitude"] is not None and eq["magnitude"] >= min_mag]
        
    if "magnitude_max" in filters:
        max_mag = filters["magnitude_max"]
        filtered = [eq for eq in filtered if eq["magnitude"] is not None and eq["magnitude"] <= max_mag]
        
    if "dias_atras" in filters:
        days = filters["dias_atras"]
        cutoff_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        cutoff_ms = cutoff_time.timestamp() * 1000
        filtered = [eq for eq in filtered if eq["time"] is not None and eq["time"] >= cutoff_ms]
        
    # Sort by time descending (newest first)
    filtered.sort(key=lambda x: x["time"] if x["time"] else 0, reverse=True)
    return filtered

def format_response(filters: dict, results: list):
    if not results:
        return "Não encontrei sismos com os critérios especificados."
        
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
        response += f"- {date_str}: Magnitude {mag} - {place}\n"
        
    return response

@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return f.read()
    return "Index not found. Please create static/index.html"

@app.post("/api/chat")
async def chat(request: ChatRequest):
    # 1. Ask LLM to extract filters
    result = await extract_filters(request.query)
    
    if result.get("status") == "error":
        return {
            "filters_extracted": {},
            "results_count": 0,
            "response": f"**Erro**: {result.get('message')}"
        }
        
    filters = result.get("filters", {})
    
    # 2. Filter local data
    results = filter_earthquakes(filters)
    
    # 3. Format response
    response_text = format_response(filters, results)
    
    return {
        "filters_extracted": filters,
        "results_count": len(results),
        "response": response_text
    }

