FROM node:24-slim AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pré-carrega o mesmo modelo ONNX all-MiniLM-L6-v2 usado pelo ChromaDB,
# mas a partir do HuggingFace e já extraído. Isto mantém a qualidade do
# DefaultEmbeddingFunction e evita o download lento do onnx.tar.gz no arranque.
RUN python - <<'PY'
from pathlib import Path
from urllib.request import urlretrieve

base_url = "https://huggingface.co/onnx-models/all-MiniLM-L6-v2-onnx/resolve/main"
target = Path.home() / ".cache" / "chroma" / "onnx_models" / "all-MiniLM-L6-v2" / "onnx"
target.mkdir(parents=True, exist_ok=True)

files = [
    "config.json",
    "model.onnx",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "vocab.txt",
]

for filename in files:
    destination = target / filename
    print(f"Downloading {filename}...")
    urlretrieve(f"{base_url}/{filename}", destination)

print(f"ChromaDB all-MiniLM-L6-v2 ONNX model cached in {target}")
PY

COPY backend/ ./
RUN rm -rf static
COPY --from=frontend-build /frontend/dist ./static

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
