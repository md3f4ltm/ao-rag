import httpx
import json
import asyncio
import os

async def fetch_earthquakes():
    print("Fetching earthquake data from USGS...")
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_month.geojson"
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        
    features = data.get("features", [])
    earthquakes = []
    
    for feature in features:
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [])
        
        earthquakes.append({
            "id": feature.get("id"),
            "place": props.get("place"),
            "magnitude": props.get("mag"),
            "time": props.get("time"),
            "url": props.get("url"),
            "longitude": coords[0] if len(coords) > 0 else None,
            "latitude": coords[1] if len(coords) > 1 else None,
            "depth": coords[2] if len(coords) > 2 else None
        })
        
    # Save to json file
    filepath = os.path.join(os.path.dirname(__file__), "earthquakes.json")
    with open(filepath, "w") as f:
        json.dump(earthquakes, f, indent=2)
        
    print(f"Saved {len(earthquakes)} earthquakes to {filepath}")

if __name__ == "__main__":
    asyncio.run(fetch_earthquakes())
