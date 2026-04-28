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

COPY backend/ ./
RUN rm -rf static
COPY --from=frontend-build /frontend/dist ./static

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
